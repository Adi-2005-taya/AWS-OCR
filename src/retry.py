"""Retry mechanisms for OCR Document Extraction System

This module provides exponential backoff retry logic for upload failures
and a retry queue for indexing failures.

Requirements: 7.1, 7.3, 4.4
"""

import time
import threading
import structlog
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeVar
from uuid import UUID

from src.constants import (
    DEFAULT_RETRY_EXPONENTIAL_BASE,
    DEFAULT_RETRY_INITIAL_DELAY,
    DEFAULT_RETRY_MAX_ATTEMPTS,
    DEFAULT_RETRY_MAX_DELAY,
)
from src.exceptions import RetryableError, RetryExhaustedError

logger = structlog.get_logger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay
    """

    max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS
    initial_delay: float = DEFAULT_RETRY_INITIAL_DELAY
    max_delay: float = DEFAULT_RETRY_MAX_DELAY
    exponential_base: float = DEFAULT_RETRY_EXPONENTIAL_BASE
    jitter: bool = False


def calculate_backoff_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
) -> float:
    """Calculate exponential backoff delay for a given attempt.

    Args:
        attempt: Current attempt number (0-indexed)
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential calculation

    Returns:
        Delay in seconds
    """
    delay = initial_delay * (exponential_base ** attempt)
    return min(delay, max_delay)


def retry_with_backoff(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,),
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute a function with exponential backoff retry.

    Args:
        func: Function to execute
        config: Retry configuration (uses defaults if not provided)
        retryable_exceptions: Tuple of exception types that trigger retry
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of func on success

    Raises:
        RetryExhaustedError: If all retry attempts are exhausted
        Exception: If a non-retryable exception occurs
    """
    cfg = config or RetryConfig()
    last_exception: Optional[Exception] = None

    for attempt in range(cfg.max_attempts):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e
            if attempt < cfg.max_attempts - 1:
                delay = calculate_backoff_delay(
                    attempt,
                    cfg.initial_delay,
                    cfg.max_delay,
                    cfg.exponential_base,
                )
                logger.warning(
                    "Operation failed, retrying",
                    attempt=attempt + 1,
                    max_attempts=cfg.max_attempts,
                    delay=delay,
                    error=str(e),
                )
                time.sleep(delay)
            else:
                logger.error(
                    "All retry attempts exhausted",
                    attempts=cfg.max_attempts,
                    error=str(e),
                )

    raise RetryExhaustedError(
        f"All {cfg.max_attempts} retry attempts exhausted",
        error_code="RETRY_EXHAUSTED",
        details={
            "max_attempts": cfg.max_attempts,
            "last_error": str(last_exception),
        },
    )


@dataclass
class RetryQueueItem:
    """An item in the retry queue.

    Attributes:
        document_id: Document to retry
        operation: Name of the operation to retry
        attempts: Number of attempts made so far
        last_error: Last error message
        next_retry_time: Timestamp when next retry should occur
    """

    document_id: UUID
    operation: str
    attempts: int = 0
    last_error: str = ""
    next_retry_time: float = field(default_factory=time.time)


class IndexingRetryQueue:
    """Retry queue for failed indexing operations.

    Implements a thread-safe queue that holds documents that failed
    indexing and schedules them for retry with exponential backoff.

    Requirements: 4.4, 7.3
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize the retry queue.

        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        self._queue: deque[RetryQueueItem] = deque()
        self._lock = threading.Lock()
        self._alert_callbacks: list[Callable[[RetryQueueItem], None]] = []
        self.logger = logger.bind(component="indexing_retry_queue")

    def enqueue(self, document_id: UUID, operation: str = "index", error: str = "") -> None:
        """Add a document to the retry queue.

        Args:
            document_id: Document that failed indexing
            operation: Name of the failed operation
            error: Error message from the failure
        """
        with self._lock:
            # Check if already in queue
            for item in self._queue:
                if item.document_id == document_id:
                    item.attempts += 1
                    item.last_error = error
                    item.next_retry_time = time.time() + calculate_backoff_delay(
                        item.attempts,
                        self.config.initial_delay,
                        self.config.max_delay,
                        self.config.exponential_base,
                    )
                    self.logger.info(
                        "Updated existing retry queue item",
                        document_id=str(document_id),
                        attempts=item.attempts,
                    )
                    return

            item = RetryQueueItem(
                document_id=document_id,
                operation=operation,
                attempts=1,
                last_error=error,
                next_retry_time=time.time() + self.config.initial_delay,
            )
            self._queue.append(item)
            self.logger.info(
                "Enqueued document for retry",
                document_id=str(document_id),
                operation=operation,
            )

            # Alert if max attempts exceeded
            if item.attempts >= self.config.max_attempts:
                self._trigger_alerts(item)

    def dequeue_ready(self) -> list[RetryQueueItem]:
        """Get all items that are ready for retry.

        Returns:
            List of items ready to be retried
        """
        now = time.time()
        ready = []

        with self._lock:
            remaining = deque()
            while self._queue:
                item = self._queue.popleft()
                if item.next_retry_time <= now and item.attempts < self.config.max_attempts:
                    ready.append(item)
                else:
                    remaining.append(item)
            self._queue = remaining

        return ready

    def remove(self, document_id: UUID) -> bool:
        """Remove a document from the retry queue (e.g., after successful retry).

        Args:
            document_id: Document to remove

        Returns:
            True if removed, False if not found
        """
        with self._lock:
            original_len = len(self._queue)
            self._queue = deque(
                item for item in self._queue if item.document_id != document_id
            )
            removed = len(self._queue) < original_len
            if removed:
                self.logger.info(
                    "Removed document from retry queue",
                    document_id=str(document_id),
                )
            return removed

    def size(self) -> int:
        """Get the number of items in the queue.

        Returns:
            Queue size
        """
        with self._lock:
            return len(self._queue)

    def register_alert_callback(self, callback: Callable[[RetryQueueItem], None]) -> None:
        """Register a callback to be called when max retries are exceeded.

        Args:
            callback: Function to call with the failed item
        """
        self._alert_callbacks.append(callback)

    def _trigger_alerts(self, item: RetryQueueItem) -> None:
        """Trigger alert callbacks for a failed item.

        Args:
            item: The item that exceeded max retries
        """
        self.logger.error(
            "Document exceeded max retry attempts - alerting monitoring",
            document_id=str(item.document_id),
            attempts=item.attempts,
            last_error=item.last_error,
        )
        for callback in self._alert_callbacks:
            try:
                callback(item)
            except Exception as e:
                self.logger.error(
                    "Alert callback failed",
                    error=str(e),
                )

    def get_all(self) -> list[RetryQueueItem]:
        """Get all items currently in the queue (for inspection).

        Returns:
            Copy of all queue items
        """
        with self._lock:
            return list(self._queue)


# Global retry queue instance
_retry_queue: Optional[IndexingRetryQueue] = None


def get_retry_queue() -> IndexingRetryQueue:
    """Get the global indexing retry queue.

    Returns:
        IndexingRetryQueue singleton
    """
    global _retry_queue
    if _retry_queue is None:
        _retry_queue = IndexingRetryQueue()
    return _retry_queue


def reset_retry_queue() -> None:
    """Reset the global retry queue (for testing)."""
    global _retry_queue
    _retry_queue = None

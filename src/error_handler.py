"""Error handling and notification for DocuSense System

This module provides comprehensive error logging with context and user
notification for OCR failures.

Requirements: 2.6, 6.4, 7.2, 7.4
"""

import structlog
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from src.constants import DocumentStatus
from src.exceptions import OCRSystemError

logger = structlog.get_logger(__name__)


@dataclass
class ErrorRecord:
    """Record of an error that occurred during document processing.

    Attributes:
        document_id: Document that encountered the error
        error_code: Machine-readable error code
        error_message: Human-readable error message
        error_type: Exception class name
        stage: Processing stage where error occurred
        timestamp: When the error occurred
        details: Additional error context
    """

    document_id: UUID
    error_code: str
    error_message: str
    error_type: str
    stage: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: Dict[str, Any] = field(default_factory=dict)


class ErrorNotifier:
    """Handles error notifications for document processing failures.

    Supports pluggable notification backends (email, webhook, etc.)
    via registered callbacks.

    Requirements: 2.6, 7.2
    """

    def __init__(self) -> None:
        """Initialize the error notifier."""
        self._callbacks: List[Callable[[ErrorRecord], None]] = []
        self.logger = logger.bind(component="error_notifier")

    def register_callback(self, callback: Callable[[ErrorRecord], None]) -> None:
        """Register a notification callback.

        Args:
            callback: Function to call when an error occurs
        """
        self._callbacks.append(callback)

    def notify(self, record: ErrorRecord) -> None:
        """Send error notification to all registered callbacks.

        Args:
            record: Error record to notify about
        """
        self.logger.info(
            "Sending error notification",
            document_id=str(record.document_id),
            error_code=record.error_code,
            stage=record.stage,
        )
        for callback in self._callbacks:
            try:
                callback(record)
            except Exception as e:
                self.logger.error(
                    "Notification callback failed",
                    error=str(e),
                )


class ErrorLogger:
    """Comprehensive error logger with structured context.

    Logs errors with full context for debugging, and stores error
    details so they can be retrieved for FAILED documents.

    Requirements: 6.4, 7.4
    """

    def __init__(self, notifier: Optional[ErrorNotifier] = None) -> None:
        """Initialize the error logger.

        Args:
            notifier: Optional notifier for sending alerts
        """
        self.notifier = notifier or ErrorNotifier()
        self._error_store: Dict[UUID, List[ErrorRecord]] = {}
        self.logger = logger.bind(component="error_logger")

    def log_error(
        self,
        document_id: UUID,
        error: Exception,
        stage: str,
        extra_details: Optional[Dict[str, Any]] = None,
    ) -> ErrorRecord:
        """Log an error with full context and store it for retrieval.

        Args:
            document_id: Document that encountered the error
            error: The exception that occurred
            stage: Processing stage (e.g., "ocr", "indexing", "upload")
            extra_details: Additional context to include

        Returns:
            ErrorRecord that was created and stored
        """
        error_code = getattr(error, "error_code", type(error).__name__)
        details = {**(getattr(error, "details", {})), **(extra_details or {})}

        record = ErrorRecord(
            document_id=document_id,
            error_code=error_code,
            error_message=str(error),
            error_type=type(error).__name__,
            stage=stage,
            details=details,
        )

        # Structured log with full context
        self.logger.error(
            "Document processing error",
            document_id=str(document_id),
            error_code=error_code,
            error_message=record.error_message,
            error_type=record.error_type,
            stage=stage,
            details=details,
        )

        # Store for later retrieval
        if document_id not in self._error_store:
            self._error_store[document_id] = []
        self._error_store[document_id].append(record)

        # Notify if this is an OCR failure (requirement 7.2)
        if stage == "ocr":
            self.notifier.notify(record)

        return record

    def get_errors(self, document_id: UUID) -> List[ErrorRecord]:
        """Get all error records for a document.

        Args:
            document_id: Document to get errors for

        Returns:
            List of error records (empty if none)
        """
        return list(self._error_store.get(document_id, []))

    def get_latest_error(self, document_id: UUID) -> Optional[ErrorRecord]:
        """Get the most recent error for a document.

        Args:
            document_id: Document to get error for

        Returns:
            Most recent ErrorRecord, or None if no errors
        """
        errors = self._error_store.get(document_id, [])
        return errors[-1] if errors else None

    def has_errors(self, document_id: UUID) -> bool:
        """Check if a document has any recorded errors.

        Args:
            document_id: Document to check

        Returns:
            True if errors exist
        """
        return bool(self._error_store.get(document_id))

    def clear_errors(self, document_id: UUID) -> None:
        """Clear all errors for a document (e.g., after successful retry).

        Args:
            document_id: Document to clear errors for
        """
        self._error_store.pop(document_id, None)


# Global error logger instance
_error_logger: Optional[ErrorLogger] = None


def get_error_logger() -> ErrorLogger:
    """Get the global error logger instance.

    Returns:
        ErrorLogger singleton
    """
    global _error_logger
    if _error_logger is None:
        _error_logger = ErrorLogger()
    return _error_logger


def reset_error_logger() -> None:
    """Reset the global error logger (for testing)."""
    global _error_logger
    _error_logger = None

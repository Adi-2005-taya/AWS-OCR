"""Tests for retry mechanisms

Requirements: 7.1, 7.3, 4.4
"""

import time
from uuid import uuid4

import pytest

from src.retry import (
    IndexingRetryQueue,
    RetryConfig,
    RetryQueueItem,
    calculate_backoff_delay,
    get_retry_queue,
    reset_retry_queue,
    retry_with_backoff,
)
from src.exceptions import RetryExhaustedError


class TestCalculateBackoffDelay:
    """Tests for calculate_backoff_delay function."""

    def test_first_attempt_uses_initial_delay(self):
        delay = calculate_backoff_delay(0, initial_delay=1.0, max_delay=60.0, exponential_base=2.0)
        assert delay == 1.0

    def test_second_attempt_doubles_delay(self):
        delay = calculate_backoff_delay(1, initial_delay=1.0, max_delay=60.0, exponential_base=2.0)
        assert delay == 2.0

    def test_third_attempt_quadruples_delay(self):
        delay = calculate_backoff_delay(2, initial_delay=1.0, max_delay=60.0, exponential_base=2.0)
        assert delay == 4.0

    def test_delay_capped_at_max(self):
        delay = calculate_backoff_delay(10, initial_delay=1.0, max_delay=60.0, exponential_base=2.0)
        assert delay == 60.0

    def test_custom_base(self):
        delay = calculate_backoff_delay(2, initial_delay=1.0, max_delay=100.0, exponential_base=3.0)
        assert delay == 9.0

    def test_custom_initial_delay(self):
        delay = calculate_backoff_delay(0, initial_delay=2.5, max_delay=60.0, exponential_base=2.0)
        assert delay == 2.5


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_succeeds_on_first_attempt(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            return "success"

        result = retry_with_backoff(func, RetryConfig(max_attempts=3, initial_delay=0))
        assert result == "success"
        assert call_count[0] == 1

    def test_retries_on_failure_then_succeeds(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("temporary failure")
            return "success"

        config = RetryConfig(max_attempts=3, initial_delay=0)
        result = retry_with_backoff(func, config)
        assert result == "success"
        assert call_count[0] == 3

    def test_raises_retry_exhausted_after_max_attempts(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            raise ValueError("always fails")

        config = RetryConfig(max_attempts=3, initial_delay=0)
        with pytest.raises(RetryExhaustedError) as exc_info:
            retry_with_backoff(func, config)

        assert call_count[0] == 3
        assert "3" in str(exc_info.value)

    def test_does_not_retry_non_retryable_exceptions(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            raise TypeError("not retryable")

        config = RetryConfig(max_attempts=3, initial_delay=0)
        with pytest.raises(TypeError):
            retry_with_backoff(func, config, retryable_exceptions=(ValueError,))

        assert call_count[0] == 1

    def test_retries_only_specified_exceptions(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("retryable")
            return "ok"

        config = RetryConfig(max_attempts=3, initial_delay=0)
        result = retry_with_backoff(func, config, retryable_exceptions=(ValueError,))
        assert result == "ok"
        assert call_count[0] == 2

    def test_passes_args_and_kwargs(self):
        def func(a, b, c=None):
            return (a, b, c)

        config = RetryConfig(max_attempts=1, initial_delay=0)
        result = retry_with_backoff(func, config, Exception, 1, 2, c=3)
        assert result == (1, 2, 3)

    def test_uses_default_config_when_none_provided(self):
        call_count = [0]

        def func():
            call_count[0] += 1
            return "ok"

        result = retry_with_backoff(func)
        assert result == "ok"


class TestIndexingRetryQueue:
    """Tests for IndexingRetryQueue."""

    def test_queue_initialization(self):
        queue = IndexingRetryQueue()
        assert queue.size() == 0

    def test_enqueue_adds_item(self):
        queue = IndexingRetryQueue()
        doc_id = uuid4()

        queue.enqueue(doc_id, operation="index", error="test error")

        assert queue.size() == 1

    def test_enqueue_multiple_documents(self):
        queue = IndexingRetryQueue()

        for _ in range(3):
            queue.enqueue(uuid4(), operation="index")

        assert queue.size() == 3

    def test_enqueue_same_document_updates_existing(self):
        queue = IndexingRetryQueue()
        doc_id = uuid4()

        queue.enqueue(doc_id, operation="index", error="first error")
        queue.enqueue(doc_id, operation="index", error="second error")

        assert queue.size() == 1
        items = queue.get_all()
        assert items[0].last_error == "second error"
        assert items[0].attempts == 2

    def test_dequeue_ready_returns_items_past_retry_time(self):
        config = RetryConfig(initial_delay=0, max_attempts=5)
        queue = IndexingRetryQueue(config=config)
        doc_id = uuid4()

        queue.enqueue(doc_id, operation="index")

        # Items with delay=0 should be immediately ready
        ready = queue.dequeue_ready()
        assert len(ready) == 1
        assert ready[0].document_id == doc_id

    def test_dequeue_ready_does_not_return_future_items(self):
        config = RetryConfig(initial_delay=9999, max_attempts=5)
        queue = IndexingRetryQueue(config=config)
        doc_id = uuid4()

        queue.enqueue(doc_id, operation="index")

        ready = queue.dequeue_ready()
        assert len(ready) == 0
        assert queue.size() == 1  # Still in queue

    def test_dequeue_ready_removes_items_from_queue(self):
        config = RetryConfig(initial_delay=0, max_attempts=5)
        queue = IndexingRetryQueue(config=config)
        doc_id = uuid4()

        queue.enqueue(doc_id, operation="index")
        queue.dequeue_ready()

        assert queue.size() == 0

    def test_remove_document_from_queue(self):
        queue = IndexingRetryQueue()
        doc_id = uuid4()

        queue.enqueue(doc_id, operation="index")
        removed = queue.remove(doc_id)

        assert removed is True
        assert queue.size() == 0

    def test_remove_nonexistent_document_returns_false(self):
        queue = IndexingRetryQueue()

        removed = queue.remove(uuid4())

        assert removed is False

    def test_alert_callback_triggered_when_max_attempts_exceeded(self):
        config = RetryConfig(max_attempts=1, initial_delay=0)
        queue = IndexingRetryQueue(config=config)

        alerts = []
        queue.register_alert_callback(lambda item: alerts.append(item))

        doc_id = uuid4()
        queue.enqueue(doc_id, operation="index", error="failed")

        assert len(alerts) == 1
        assert alerts[0].document_id == doc_id

    def test_multiple_alert_callbacks(self):
        config = RetryConfig(max_attempts=1, initial_delay=0)
        queue = IndexingRetryQueue(config=config)

        alerts1 = []
        alerts2 = []
        queue.register_alert_callback(lambda item: alerts1.append(item))
        queue.register_alert_callback(lambda item: alerts2.append(item))

        queue.enqueue(uuid4(), operation="index", error="failed")

        assert len(alerts1) == 1
        assert len(alerts2) == 1

    def test_get_all_returns_all_items(self):
        queue = IndexingRetryQueue()
        doc_ids = [uuid4() for _ in range(3)]

        for doc_id in doc_ids:
            queue.enqueue(doc_id, operation="index")

        items = queue.get_all()
        assert len(items) == 3
        item_doc_ids = {item.document_id for item in items}
        assert item_doc_ids == set(doc_ids)

    def test_queue_is_thread_safe(self):
        """Test that queue operations are thread-safe."""
        import threading

        config = RetryConfig(initial_delay=0, max_attempts=100)
        queue = IndexingRetryQueue(config=config)
        errors = []

        def enqueue_many():
            try:
                for _ in range(50):
                    queue.enqueue(uuid4(), operation="index")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=enqueue_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert queue.size() == 200


class TestGlobalRetryQueue:
    """Tests for global retry queue singleton."""

    def setup_method(self):
        reset_retry_queue()

    def teardown_method(self):
        reset_retry_queue()

    def test_get_retry_queue_returns_instance(self):
        queue = get_retry_queue()
        assert isinstance(queue, IndexingRetryQueue)

    def test_get_retry_queue_returns_singleton(self):
        q1 = get_retry_queue()
        q2 = get_retry_queue()
        assert q1 is q2

    def test_reset_retry_queue_creates_new_instance(self):
        q1 = get_retry_queue()
        reset_retry_queue()
        q2 = get_retry_queue()
        assert q1 is not q2


class TestRetryIntegration:
    """Integration tests for retry mechanisms."""

    def test_upload_retry_with_exponential_backoff(self):
        """Simulate upload retry with exponential backoff (req 7.1)."""
        attempts = []
        delays = []
        last_time = [time.monotonic()]

        def mock_upload():
            now = time.monotonic()
            delays.append(now - last_time[0])
            last_time[0] = now
            attempts.append(1)
            if len(attempts) < 3:
                raise ConnectionError("upload failed")
            return "uploaded"

        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.01,
            max_delay=1.0,
            exponential_base=2.0,
        )
        result = retry_with_backoff(mock_upload, config, retryable_exceptions=(ConnectionError,))

        assert result == "uploaded"
        assert len(attempts) == 3
        # Second delay should be roughly double the first
        assert delays[2] >= delays[1] * 1.5

    def test_indexing_retry_queue_workflow(self):
        """Simulate indexing failure and retry queue workflow (req 4.4, 7.3)."""
        config = RetryConfig(initial_delay=0, max_attempts=3)
        queue = IndexingRetryQueue(config=config)

        doc_id = uuid4()
        alerts = []
        queue.register_alert_callback(lambda item: alerts.append(item))

        # First failure
        queue.enqueue(doc_id, operation="index", error="connection timeout")
        assert queue.size() == 1

        # Get ready items and retry
        ready = queue.dequeue_ready()
        assert len(ready) == 1

        # Second failure - re-enqueue
        queue.enqueue(doc_id, operation="index", error="still failing")
        assert queue.size() == 1

        # Successful retry - remove from queue
        queue.remove(doc_id)
        assert queue.size() == 0
        assert len(alerts) == 0  # No alert since we succeeded before max attempts

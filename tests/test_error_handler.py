"""Tests for error handling and notification

Requirements: 2.6, 6.4, 7.2, 7.4
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.error_handler import (
    ErrorLogger,
    ErrorNotifier,
    ErrorRecord,
    get_error_logger,
    reset_error_logger,
)
from src.exceptions import DocumentProcessingError, OCRProcessingError


class TestErrorRecord:
    """Tests for ErrorRecord dataclass."""

    def test_error_record_creation(self):
        doc_id = uuid4()
        record = ErrorRecord(
            document_id=doc_id,
            error_code="OCR_FAILED",
            error_message="OCR extraction failed",
            error_type="OCRProcessingError",
            stage="ocr",
        )

        assert record.document_id == doc_id
        assert record.error_code == "OCR_FAILED"
        assert record.error_message == "OCR extraction failed"
        assert record.error_type == "OCRProcessingError"
        assert record.stage == "ocr"
        assert isinstance(record.timestamp, datetime)
        assert record.details == {}

    def test_error_record_with_details(self):
        doc_id = uuid4()
        record = ErrorRecord(
            document_id=doc_id,
            error_code="OCR_FAILED",
            error_message="failed",
            error_type="Exception",
            stage="ocr",
            details={"filename": "test.pdf", "attempt": 1},
        )

        assert record.details["filename"] == "test.pdf"
        assert record.details["attempt"] == 1

    def test_error_record_timestamp_is_utc(self):
        record = ErrorRecord(
            document_id=uuid4(),
            error_code="ERR",
            error_message="msg",
            error_type="Exception",
            stage="test",
        )
        assert record.timestamp.tzinfo is not None


class TestErrorNotifier:
    """Tests for ErrorNotifier."""

    def test_notifier_initialization(self):
        notifier = ErrorNotifier()
        assert notifier is not None

    def test_register_callback(self):
        notifier = ErrorNotifier()
        received = []

        notifier.register_callback(lambda r: received.append(r))

        record = ErrorRecord(
            document_id=uuid4(),
            error_code="ERR",
            error_message="msg",
            error_type="Exception",
            stage="test",
        )
        notifier.notify(record)

        assert len(received) == 1
        assert received[0] is record

    def test_multiple_callbacks_all_called(self):
        notifier = ErrorNotifier()
        received1 = []
        received2 = []

        notifier.register_callback(lambda r: received1.append(r))
        notifier.register_callback(lambda r: received2.append(r))

        record = ErrorRecord(
            document_id=uuid4(),
            error_code="ERR",
            error_message="msg",
            error_type="Exception",
            stage="test",
        )
        notifier.notify(record)

        assert len(received1) == 1
        assert len(received2) == 1

    def test_failing_callback_does_not_stop_others(self):
        notifier = ErrorNotifier()
        received = []

        def bad_callback(r):
            raise RuntimeError("callback failed")

        notifier.register_callback(bad_callback)
        notifier.register_callback(lambda r: received.append(r))

        record = ErrorRecord(
            document_id=uuid4(),
            error_code="ERR",
            error_message="msg",
            error_type="Exception",
            stage="test",
        )
        notifier.notify(record)  # Should not raise

        assert len(received) == 1

    def test_no_callbacks_does_not_raise(self):
        notifier = ErrorNotifier()
        record = ErrorRecord(
            document_id=uuid4(),
            error_code="ERR",
            error_message="msg",
            error_type="Exception",
            stage="test",
        )
        notifier.notify(record)  # Should not raise


class TestErrorLogger:
    """Tests for ErrorLogger."""

    def test_logger_initialization(self):
        error_logger = ErrorLogger()
        assert error_logger is not None

    def test_log_error_stores_record(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()
        error = OCRProcessingError("OCR failed", error_code="OCR_FAILED")

        record = error_logger.log_error(doc_id, error, stage="ocr")

        assert record.document_id == doc_id
        assert record.error_code == "OCR_FAILED"
        assert record.stage == "ocr"

    def test_log_error_uses_exception_error_code(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()
        error = DocumentProcessingError("failed", error_code="PROC_FAILED")

        record = error_logger.log_error(doc_id, error, stage="processing")

        assert record.error_code == "PROC_FAILED"

    def test_log_error_falls_back_to_class_name(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()
        error = ValueError("plain error")

        record = error_logger.log_error(doc_id, error, stage="test")

        assert record.error_code == "ValueError"

    def test_log_error_includes_extra_details(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()
        error = ValueError("error")

        record = error_logger.log_error(
            doc_id, error, stage="test", extra_details={"filename": "doc.pdf"}
        )

        assert record.details["filename"] == "doc.pdf"

    def test_get_errors_returns_all_errors_for_document(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()

        error_logger.log_error(doc_id, ValueError("first"), stage="ocr")
        error_logger.log_error(doc_id, ValueError("second"), stage="indexing")

        errors = error_logger.get_errors(doc_id)
        assert len(errors) == 2

    def test_get_errors_returns_empty_for_unknown_document(self):
        error_logger = ErrorLogger()

        errors = error_logger.get_errors(uuid4())
        assert errors == []

    def test_get_latest_error_returns_most_recent(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()

        error_logger.log_error(doc_id, ValueError("first"), stage="ocr")
        error_logger.log_error(doc_id, ValueError("second"), stage="indexing")

        latest = error_logger.get_latest_error(doc_id)
        assert latest is not None
        assert latest.stage == "indexing"

    def test_get_latest_error_returns_none_for_unknown_document(self):
        error_logger = ErrorLogger()

        latest = error_logger.get_latest_error(uuid4())
        assert latest is None

    def test_has_errors_returns_true_when_errors_exist(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()

        error_logger.log_error(doc_id, ValueError("error"), stage="ocr")

        assert error_logger.has_errors(doc_id) is True

    def test_has_errors_returns_false_when_no_errors(self):
        error_logger = ErrorLogger()

        assert error_logger.has_errors(uuid4()) is False

    def test_clear_errors_removes_all_errors_for_document(self):
        error_logger = ErrorLogger()
        doc_id = uuid4()

        error_logger.log_error(doc_id, ValueError("error"), stage="ocr")
        error_logger.clear_errors(doc_id)

        assert error_logger.has_errors(doc_id) is False
        assert error_logger.get_errors(doc_id) == []

    def test_clear_errors_does_not_affect_other_documents(self):
        error_logger = ErrorLogger()
        doc1_id = uuid4()
        doc2_id = uuid4()

        error_logger.log_error(doc1_id, ValueError("error"), stage="ocr")
        error_logger.log_error(doc2_id, ValueError("error"), stage="ocr")

        error_logger.clear_errors(doc1_id)

        assert not error_logger.has_errors(doc1_id)
        assert error_logger.has_errors(doc2_id)

    def test_ocr_stage_triggers_notification(self):
        notifier = ErrorNotifier()
        notifications = []
        notifier.register_callback(lambda r: notifications.append(r))

        error_logger = ErrorLogger(notifier=notifier)
        doc_id = uuid4()

        error_logger.log_error(doc_id, ValueError("ocr failed"), stage="ocr")

        assert len(notifications) == 1
        assert notifications[0].document_id == doc_id

    def test_non_ocr_stage_does_not_trigger_notification(self):
        notifier = ErrorNotifier()
        notifications = []
        notifier.register_callback(lambda r: notifications.append(r))

        error_logger = ErrorLogger(notifier=notifier)
        doc_id = uuid4()

        error_logger.log_error(doc_id, ValueError("indexing failed"), stage="indexing")

        assert len(notifications) == 0

    def test_errors_for_different_documents_are_isolated(self):
        error_logger = ErrorLogger()
        doc1_id = uuid4()
        doc2_id = uuid4()

        error_logger.log_error(doc1_id, ValueError("doc1 error"), stage="ocr")

        assert error_logger.has_errors(doc1_id)
        assert not error_logger.has_errors(doc2_id)


class TestGlobalErrorLogger:
    """Tests for global error logger singleton."""

    def setup_method(self):
        reset_error_logger()

    def teardown_method(self):
        reset_error_logger()

    def test_get_error_logger_returns_instance(self):
        el = get_error_logger()
        assert isinstance(el, ErrorLogger)

    def test_get_error_logger_returns_singleton(self):
        el1 = get_error_logger()
        el2 = get_error_logger()
        assert el1 is el2

    def test_reset_creates_new_instance(self):
        el1 = get_error_logger()
        reset_error_logger()
        el2 = get_error_logger()
        assert el1 is not el2


class TestErrorHandlingIntegration:
    """Integration tests for error handling workflow."""

    def test_full_error_logging_and_notification_workflow(self):
        """Test complete error logging with notification (req 2.6, 7.2, 7.4)."""
        notifier = ErrorNotifier()
        ocr_alerts = []
        notifier.register_callback(lambda r: ocr_alerts.append(r))

        error_logger = ErrorLogger(notifier=notifier)
        doc_id = uuid4()

        # Simulate OCR failure
        ocr_error = OCRProcessingError(
            "Tesseract failed to process image",
            error_code="OCR_PROCESSING_FAILED",
            details={"filename": "invoice.pdf", "confidence": 0.0},
        )
        error_logger.log_error(doc_id, ocr_error, stage="ocr")

        # Verify error was stored
        assert error_logger.has_errors(doc_id)
        errors = error_logger.get_errors(doc_id)
        assert len(errors) == 1
        assert errors[0].error_code == "OCR_PROCESSING_FAILED"
        assert errors[0].details["filename"] == "invoice.pdf"

        # Verify notification was sent
        assert len(ocr_alerts) == 1
        assert ocr_alerts[0].document_id == doc_id

        # Verify error details are retrievable (req 6.4)
        latest = error_logger.get_latest_error(doc_id)
        assert latest is not None
        assert latest.stage == "ocr"
        assert latest.error_type == "OCRProcessingError"

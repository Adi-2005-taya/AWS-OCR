"""Tests for status management layer

Requirements: 4.2, 6.2
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.constants import DocumentStatus
from src.exceptions import DocumentNotFoundError, InvalidDocumentStatusError
from src.models import Document
from src.status_manager import (
    StatusChangeEvent,
    StatusManager,
    get_status_manager,
    reset_status_manager,
)


def make_document(status=DocumentStatus.UPLOADED) -> Document:
    return Document(
        id=uuid4(),
        filename="test.pdf",
        storageUrl="file:///test.pdf",
        contentType="application/pdf",
        status=status,
    )


class TestStatusChangeEvent:
    def test_event_creation(self):
        doc_id = uuid4()
        event = StatusChangeEvent(
            document_id=doc_id,
            old_status=DocumentStatus.UPLOADED,
            new_status=DocumentStatus.PROCESSING,
        )
        assert event.document_id == doc_id
        assert event.old_status == DocumentStatus.UPLOADED
        assert event.new_status == DocumentStatus.PROCESSING
        assert isinstance(event.timestamp, datetime)

    def test_event_timestamp_is_utc(self):
        event = StatusChangeEvent(
            document_id=uuid4(),
            old_status=None,
            new_status=DocumentStatus.UPLOADED,
        )
        assert event.timestamp.tzinfo is not None


class TestStatusManager:
    def test_register_document(self):
        sm = StatusManager()
        doc = make_document()
        sm.register(doc)
        assert sm.is_registered(doc.id)

    def test_get_status_after_register(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        assert sm.get_status(doc.id) == DocumentStatus.UPLOADED

    def test_get_status_raises_for_unknown_document(self):
        sm = StatusManager()
        with pytest.raises(DocumentNotFoundError):
            sm.get_status(uuid4())

    def test_transition_uploaded_to_processing(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        event = sm.transition(doc.id, DocumentStatus.PROCESSING)
        assert sm.get_status(doc.id) == DocumentStatus.PROCESSING
        assert event.old_status == DocumentStatus.UPLOADED
        assert event.new_status == DocumentStatus.PROCESSING

    def test_transition_processing_to_indexed(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        sm.transition(doc.id, DocumentStatus.PROCESSING)
        sm.transition(doc.id, DocumentStatus.INDEXED)
        assert sm.get_status(doc.id) == DocumentStatus.INDEXED

    def test_transition_processing_to_failed(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        sm.transition(doc.id, DocumentStatus.PROCESSING)
        sm.transition(doc.id, DocumentStatus.FAILED)
        assert sm.get_status(doc.id) == DocumentStatus.FAILED

    def test_transition_uploaded_to_failed(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        sm.transition(doc.id, DocumentStatus.FAILED)
        assert sm.get_status(doc.id) == DocumentStatus.FAILED

    def test_invalid_transition_raises_error(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        with pytest.raises(InvalidDocumentStatusError):
            sm.transition(doc.id, DocumentStatus.INDEXED)  # must go through PROCESSING

    def test_indexed_is_terminal_state(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        sm.transition(doc.id, DocumentStatus.PROCESSING)
        sm.transition(doc.id, DocumentStatus.INDEXED)
        with pytest.raises(InvalidDocumentStatusError):
            sm.transition(doc.id, DocumentStatus.PROCESSING)

    def test_transition_without_validation(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        # Skip directly to INDEXED without going through PROCESSING
        sm.transition(doc.id, DocumentStatus.INDEXED, validate=False)
        assert sm.get_status(doc.id) == DocumentStatus.INDEXED

    def test_index_timestamp_recorded_on_indexed(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        sm.transition(doc.id, DocumentStatus.PROCESSING)

        before = datetime.now(UTC)
        sm.transition(doc.id, DocumentStatus.INDEXED)
        after = datetime.now(UTC)

        ts = sm.get_index_timestamp(doc.id)
        assert ts is not None
        assert before <= ts <= after

    def test_index_timestamp_none_before_indexing(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        assert sm.get_index_timestamp(doc.id) is None

    def test_change_log_records_all_transitions(self):
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)
        sm.transition(doc.id, DocumentStatus.PROCESSING)
        sm.transition(doc.id, DocumentStatus.INDEXED)

        log = sm.get_change_log(doc.id)
        assert len(log) == 2
        assert log[0].new_status == DocumentStatus.PROCESSING
        assert log[1].new_status == DocumentStatus.INDEXED

    def test_change_log_filtered_by_document(self):
        sm = StatusManager()
        doc1 = make_document()
        doc2 = make_document()
        sm.register(doc1)
        sm.register(doc2)
        sm.transition(doc1.id, DocumentStatus.PROCESSING)
        sm.transition(doc2.id, DocumentStatus.FAILED)

        log1 = sm.get_change_log(doc1.id)
        log2 = sm.get_change_log(doc2.id)
        assert len(log1) == 1
        assert len(log2) == 1

    def test_get_change_log_all_documents(self):
        sm = StatusManager()
        doc1 = make_document()
        doc2 = make_document()
        sm.register(doc1)
        sm.register(doc2)
        sm.transition(doc1.id, DocumentStatus.PROCESSING)
        sm.transition(doc2.id, DocumentStatus.FAILED)

        log = sm.get_change_log()
        assert len(log) == 2

    def test_change_callback_invoked_on_transition(self):
        sm = StatusManager()
        doc = make_document()
        sm.register(doc)

        events = []
        sm.register_change_callback(lambda e: events.append(e))

        sm.transition(doc.id, DocumentStatus.PROCESSING)

        assert len(events) == 1
        assert events[0].new_status == DocumentStatus.PROCESSING

    def test_multiple_change_callbacks(self):
        sm = StatusManager()
        doc = make_document()
        sm.register(doc)

        cb1, cb2 = [], []
        sm.register_change_callback(lambda e: cb1.append(e))
        sm.register_change_callback(lambda e: cb2.append(e))

        sm.transition(doc.id, DocumentStatus.PROCESSING)

        assert len(cb1) == 1
        assert len(cb2) == 1

    def test_failing_callback_does_not_stop_transition(self):
        sm = StatusManager()
        doc = make_document()
        sm.register(doc)

        sm.register_change_callback(lambda e: (_ for _ in ()).throw(RuntimeError("boom")))

        # Should not raise
        sm.transition(doc.id, DocumentStatus.PROCESSING)
        assert sm.get_status(doc.id) == DocumentStatus.PROCESSING

    def test_is_registered_false_for_unknown(self):
        sm = StatusManager()
        assert sm.is_registered(uuid4()) is False


class TestGlobalStatusManager:
    def setup_method(self):
        reset_status_manager()

    def teardown_method(self):
        reset_status_manager()

    def test_get_status_manager_returns_instance(self):
        sm = get_status_manager()
        assert isinstance(sm, StatusManager)

    def test_get_status_manager_is_singleton(self):
        sm1 = get_status_manager()
        sm2 = get_status_manager()
        assert sm1 is sm2

    def test_reset_creates_new_instance(self):
        sm1 = get_status_manager()
        reset_status_manager()
        sm2 = get_status_manager()
        assert sm1 is not sm2


class TestStatusManagerIntegration:
    def test_full_document_lifecycle(self):
        """Test complete UPLOADED → PROCESSING → INDEXED lifecycle."""
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)

        events = []
        sm.register_change_callback(lambda e: events.append(e))

        sm.transition(doc.id, DocumentStatus.PROCESSING)
        sm.transition(doc.id, DocumentStatus.INDEXED)

        assert sm.get_status(doc.id) == DocumentStatus.INDEXED
        assert sm.get_index_timestamp(doc.id) is not None
        assert len(events) == 2
        assert len(sm.get_change_log(doc.id)) == 2

    def test_failed_document_lifecycle(self):
        """Test UPLOADED → PROCESSING → FAILED lifecycle."""
        sm = StatusManager()
        doc = make_document(DocumentStatus.UPLOADED)
        sm.register(doc)

        sm.transition(doc.id, DocumentStatus.PROCESSING)
        sm.transition(doc.id, DocumentStatus.FAILED)

        assert sm.get_status(doc.id) == DocumentStatus.FAILED
        assert sm.get_index_timestamp(doc.id) is None

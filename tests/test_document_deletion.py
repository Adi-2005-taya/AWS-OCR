"""Tests for document deletion service

Requirements: 10.4
"""

from uuid import uuid4

import pytest

from src.document_deletion import (
    DeletionResult,
    DocumentDeletionService,
    create_deletion_service,
)
from src.models import IndexedDocument


class MockStorage:
    def __init__(self, has_document=True, should_fail=False):
        self.has_document = has_document
        self.should_fail = should_fail
        self.deleted_ids = []

    def delete(self, document_id):
        if self.should_fail:
            raise Exception("storage error")
        if document_id in self.deleted_ids:
            return False
        if self.has_document:
            self.deleted_ids.append(document_id)
            return True
        return False


class MockSearchEngine:
    def __init__(self, has_document=True, should_fail=False):
        self.has_document = has_document
        self.should_fail = should_fail
        self.deleted_ids = []
        self._docs = {}

    def index(self, doc):
        self._docs[doc.documentId] = doc

    def delete(self, document_id):
        if self.should_fail:
            raise Exception("index error")
        if document_id in self.deleted_ids:
            return False
        if self.has_document or document_id in self._docs:
            self.deleted_ids.append(document_id)
            self._docs.pop(document_id, None)
            return True
        return False


class TestDeletionResult:
    def test_success_when_both_deleted(self):
        doc_id = uuid4()
        result = DeletionResult(doc_id, storage_deleted=True, index_deleted=True)
        assert result.success is True
        assert result.error is None

    def test_failure_when_storage_not_deleted(self):
        result = DeletionResult(uuid4(), storage_deleted=False, index_deleted=True)
        assert result.success is False

    def test_failure_when_index_not_deleted(self):
        result = DeletionResult(uuid4(), storage_deleted=True, index_deleted=False)
        assert result.success is False

    def test_error_message_stored(self):
        result = DeletionResult(uuid4(), storage_deleted=False, index_deleted=False, error="oops")
        assert result.error == "oops"


class TestDocumentDeletionService:
    def test_successful_deletion(self):
        doc_id = uuid4()
        storage = MockStorage(has_document=True)
        engine = MockSearchEngine(has_document=True)

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        assert result.success is True
        assert result.storage_deleted is True
        assert result.index_deleted is True
        assert doc_id in storage.deleted_ids
        assert doc_id in engine.deleted_ids

    def test_document_not_in_storage(self):
        doc_id = uuid4()
        storage = MockStorage(has_document=False)
        engine = MockSearchEngine(has_document=True)

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        assert result.storage_deleted is False
        assert result.index_deleted is True
        assert result.success is False

    def test_document_not_in_index(self):
        doc_id = uuid4()
        storage = MockStorage(has_document=True)
        engine = MockSearchEngine(has_document=False)

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        assert result.storage_deleted is True
        assert result.index_deleted is False
        assert result.success is False

    def test_storage_error_still_attempts_index_deletion(self):
        doc_id = uuid4()
        storage = MockStorage(should_fail=True)
        engine = MockSearchEngine(has_document=True)

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        # Storage failed but index deletion was still attempted
        assert result.storage_deleted is False
        assert result.index_deleted is True
        assert result.success is False
        assert result.error is not None
        assert "storage" in result.error

    def test_index_error_still_reports_storage_success(self):
        doc_id = uuid4()
        storage = MockStorage(has_document=True)
        engine = MockSearchEngine(should_fail=True)

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        assert result.storage_deleted is True
        assert result.index_deleted is False
        assert result.success is False
        assert "index" in result.error

    def test_both_operations_fail(self):
        doc_id = uuid4()
        storage = MockStorage(should_fail=True)
        engine = MockSearchEngine(should_fail=True)

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        assert result.success is False
        assert "storage" in result.error
        assert "index" in result.error

    def test_document_id_in_result(self):
        doc_id = uuid4()
        storage = MockStorage()
        engine = MockSearchEngine()

        svc = DocumentDeletionService(storage=storage, search_engine=engine)
        result = svc.delete(doc_id)

        assert result.document_id == doc_id


class TestCreateDeletionService:
    def test_factory_returns_service(self):
        storage = MockStorage()
        engine = MockSearchEngine()
        svc = create_deletion_service(storage=storage, search_engine=engine)
        assert isinstance(svc, DocumentDeletionService)


class TestDocumentDeletionIntegration:
    def test_delete_removes_from_both_storage_and_index(self):
        """Full deletion workflow: index a doc, then delete it."""
        from src.search_engine import InMemorySearchEngine
        from src.storage import LocalFileSystemStorage
        import tempfile, io

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = LocalFileSystemStorage(base_path=tmpdir, encryption_enabled=False)
            engine = InMemorySearchEngine()

            # Upload a document
            doc_id, _ = storage.upload(
                io.BytesIO(b"test content"), "test.pdf", "application/pdf"
            )

            # Index it
            indexed = IndexedDocument(
                documentId=doc_id,
                cleanedText="test content",
                keywords=["test"],
                searchableContent="test content",
            )
            engine.index(indexed)

            assert storage.exists(doc_id)
            assert engine.exists(doc_id)

            # Delete
            svc = DocumentDeletionService(storage=storage, search_engine=engine)
            result = svc.delete(doc_id)

            assert result.success is True
            assert not storage.exists(doc_id)
            assert not engine.exists(doc_id)

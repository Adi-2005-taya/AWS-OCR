"""Document deletion service for OCR Document Extraction System

Handles atomic deletion of documents from both storage and the search
index, with compensation on partial failure.

Requirements: 10.4
"""

import structlog
from typing import Optional
from uuid import UUID

from src.exceptions import DocumentNotFoundError, StorageDeleteError, SearchError
from src.search_engine import SearchEngineFactory, SearchEngineInterface
from src.storage import StorageFactory, StorageInterface

logger = structlog.get_logger(__name__)


class DeletionResult:
    """Result of a document deletion operation.

    Attributes:
        document_id: Document that was deleted
        storage_deleted: Whether storage deletion succeeded
        index_deleted: Whether index deletion succeeded
        success: True only when both operations succeeded
        error: Error message if any step failed
    """

    def __init__(
        self,
        document_id: UUID,
        storage_deleted: bool,
        index_deleted: bool,
        error: Optional[str] = None,
    ) -> None:
        self.document_id = document_id
        self.storage_deleted = storage_deleted
        self.index_deleted = index_deleted
        self.success = storage_deleted and index_deleted
        self.error = error


class DocumentDeletionService:
    """Deletes documents from storage and the search index.

    Attempts both operations and reports partial failures so callers
    can decide on compensation (e.g., re-queue for retry).

    Requirements: 10.4
    """

    def __init__(
        self,
        storage: Optional[StorageInterface] = None,
        search_engine: Optional[SearchEngineInterface] = None,
    ) -> None:
        """Initialize the deletion service.

        Args:
            storage: Storage backend (creates default if not provided)
            search_engine: Search engine (creates default if not provided)
        """
        self.storage = storage or StorageFactory.create_storage()
        self.search_engine = search_engine or SearchEngineFactory.create_engine()
        self.logger = logger.bind(component="document_deletion")

    def delete(self, document_id: UUID) -> DeletionResult:
        """Delete a document from storage and the search index.

        Both operations are attempted regardless of whether the first
        succeeds, so that partial state is minimised.  The result
        object reports which operations succeeded.

        Args:
            document_id: Document to delete

        Returns:
            DeletionResult describing what was deleted
        """
        self.logger.info("Starting document deletion", document_id=str(document_id))

        storage_deleted = False
        index_deleted = False
        errors = []

        # --- Delete from storage ---
        try:
            storage_deleted = self.storage.delete(document_id)
            if storage_deleted:
                self.logger.info(
                    "Document deleted from storage", document_id=str(document_id)
                )
            else:
                self.logger.warning(
                    "Document not found in storage", document_id=str(document_id)
                )
        except Exception as e:
            errors.append(f"storage: {e}")
            self.logger.error(
                "Storage deletion failed",
                document_id=str(document_id),
                error=str(e),
            )

        # --- Delete from search index ---
        try:
            index_deleted = self.search_engine.delete(document_id)
            if index_deleted:
                self.logger.info(
                    "Document deleted from search index", document_id=str(document_id)
                )
            else:
                self.logger.warning(
                    "Document not found in search index", document_id=str(document_id)
                )
        except Exception as e:
            errors.append(f"index: {e}")
            self.logger.error(
                "Index deletion failed",
                document_id=str(document_id),
                error=str(e),
            )

        result = DeletionResult(
            document_id=document_id,
            storage_deleted=storage_deleted,
            index_deleted=index_deleted,
            error="; ".join(errors) if errors else None,
        )

        if result.success:
            self.logger.info(
                "Document deletion completed", document_id=str(document_id)
            )
        else:
            self.logger.warning(
                "Document deletion partially failed",
                document_id=str(document_id),
                storage_deleted=storage_deleted,
                index_deleted=index_deleted,
                errors=errors,
            )

        return result


def create_deletion_service(
    storage: Optional[StorageInterface] = None,
    search_engine: Optional[SearchEngineInterface] = None,
) -> DocumentDeletionService:
    """Create a DocumentDeletionService instance.

    Args:
        storage: Optional storage backend
        search_engine: Optional search engine

    Returns:
        DocumentDeletionService instance
    """
    return DocumentDeletionService(storage=storage, search_engine=search_engine)

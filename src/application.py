"""Application entry points for DocuSense System

Wires all components together and exposes high-level handlers for:
- Document upload
- Document search
- Document status query
- Document deletion

Requirements: 1.1, 2.2, 5.1, 6.1, 8.1, 10.4
"""

import io
import structlog
from typing import List, Optional
from uuid import UUID

from src.cache import DocumentCache, get_document_cache
from src.constants import DocumentStatus
from src.document_deletion import DocumentDeletionService, DeletionResult
from src.document_processor import DocumentProcessor
from src.error_handler import ErrorLogger, get_error_logger
from src.exceptions import (
    DocumentNotFoundError,
    InvalidFileTypeError,
    MalwareDetectedError,
)
from src.models import Document, IndexedDocument
from src.ocr_service import OCRServiceInterface
from src.query_handler import AuthorizationProvider, QueryHandler, QueryResult
from src.retry import IndexingRetryQueue, RetryConfig, get_retry_queue
from src.search_engine import SearchEngineInterface
from src.status_manager import StatusManager, get_status_manager
from src.storage import StorageInterface
from src.storage_monitor import StorageMonitor
from src.text_cleaner import TextCleaner
from src.validation import FileTypeValidator

logger = structlog.get_logger(__name__)


class UploadResult:
    """Result of a document upload operation."""

    def __init__(self, document_id: UUID, storage_url: str, status: DocumentStatus) -> None:
        self.document_id = document_id
        self.storage_url = storage_url
        self.status = status


class StatusResult:
    """Result of a status query."""

    def __init__(
        self,
        document_id: UUID,
        status: DocumentStatus,
        error_details: Optional[dict] = None,
    ) -> None:
        self.document_id = document_id
        self.status = status
        self.error_details = error_details


class OCRApplication:
    """Top-level application that wires all components together.

    Provides upload, search, status, and deletion handlers.

    Requirements: 1.1, 2.2, 5.1, 6.1, 8.1, 10.4
    """

    def __init__(
        self,
        storage: StorageInterface,
        ocr_service: OCRServiceInterface,
        text_cleaner: TextCleaner,
        search_engine: SearchEngineInterface,
        status_manager: Optional[StatusManager] = None,
        document_cache: Optional[DocumentCache] = None,
        error_logger: Optional[ErrorLogger] = None,
        retry_queue: Optional[IndexingRetryQueue] = None,
        authorization_provider: Optional[AuthorizationProvider] = None,
        file_validator: Optional[FileTypeValidator] = None,
    ) -> None:
        self.storage = storage
        self.ocr_service = ocr_service
        self.text_cleaner = text_cleaner
        self.search_engine = search_engine
        self.status_manager = status_manager or get_status_manager()
        self.document_cache = document_cache or get_document_cache()
        self.error_logger = error_logger or get_error_logger()
        self.retry_queue = retry_queue or get_retry_queue()
        self.file_validator = file_validator or FileTypeValidator()

        # Build sub-services
        self._processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine,
        )
        self._query_handler = QueryHandler(
            search_engine=search_engine,
            storage_url_provider=lambda doc_id: self._safe_get_url(doc_id),
            authorization_provider=authorization_provider,
        )
        self._deletion_service = DocumentDeletionService(
            storage=storage,
            search_engine=search_engine,
        )

        # Storage monitor wired to processor
        self._monitor = StorageMonitor()
        self._monitor.register_handler(self._on_upload_event)

        self.logger = logger.bind(component="ocr_application")

    # ------------------------------------------------------------------
    # Upload handler
    # ------------------------------------------------------------------

    def upload(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        owner_id: str | None = None,
    ) -> UploadResult:
        """Upload a document and trigger async processing.

        Validates file type, scans for malware (via storage), stores the
        file, registers it with the status manager, and fires the upload
        event so the storage monitor triggers processing.

        Args:
            file_data: Raw file bytes
            filename: Original filename
            content_type: MIME content type

        Returns:
            UploadResult with document_id, storage_url, and status

        Raises:
            InvalidFileTypeError: If content_type is not allowed
        """
        self.logger.info("Uploading document", filename=filename, content_type=content_type)

        # Validate file type
        self.file_validator.validate(content_type)

        # Upload to storage (malware scan happens inside storage)
        document_id, storage_url = self.storage.upload(
            io.BytesIO(file_data), filename, content_type
        )

        # Create document model
        document = Document(
            id=document_id,
            filename=filename,
            storageUrl=storage_url,
            contentType=content_type,
            status=DocumentStatus.UPLOADED,
            ownerId=owner_id,
        )

        # Register with status manager
        self.status_manager.register(document)

        # Cache the document
        self.document_cache.set(document)

        self.logger.info(
            "Document uploaded",
            document_id=str(document_id),
            storage_url=storage_url,
        )

        # Trigger storage monitor event (fires processing pipeline) in a background thread
        # This makes the upload API non-blocking and instant
        from src.storage_monitor import UploadEvent
        from datetime import UTC, datetime
        import threading
        
        event = UploadEvent(
            document_id=document_id,
            filename=filename,
            content_type=content_type,
            upload_timestamp=datetime.now(UTC),
            metadata={"source": "api_upload"},
            owner_id=owner_id,
            storage_url=storage_url,
        )
        
        threading.Thread(
            target=self._monitor.on_file_uploaded,
            args=(event,),
            daemon=True
        ).start()
        
        return UploadResult(
            document_id=document_id,
            storage_url=storage_url,
            status=DocumentStatus.UPLOADED,
        )

    # ------------------------------------------------------------------
    # Search handler
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        limit: int = 10,
        user_id: Optional[str] = None,
    ) -> List[QueryResult]:
        """Search indexed documents.

        Args:
            query: Search query string
            limit: Maximum results to return
            user_id: Optional user ID for access control

        Returns:
            List of QueryResult objects
        """
        self.logger.info("Processing search query", query=query, user_id=user_id)
        return self._query_handler.search(query, limit=limit, user_id=user_id)

    # ------------------------------------------------------------------
    # Status handler
    # ------------------------------------------------------------------

    def get_status(self, document_id: UUID) -> StatusResult:
        """Get the processing status of a document.

        Args:
            document_id: Document to query

        Returns:
            StatusResult with current status and any error details

        Raises:
            DocumentNotFoundError: If document is not registered
        """
        status = self.status_manager.get_status(document_id)
        error_details = None

        if status == DocumentStatus.FAILED:
            latest_error = self.error_logger.get_latest_error(document_id)
            if latest_error:
                error_details = {
                    "error_code": latest_error.error_code,
                    "error_message": latest_error.error_message,
                    "stage": latest_error.stage,
                    "timestamp": latest_error.timestamp.isoformat(),
                }

        return StatusResult(
            document_id=document_id,
            status=status,
            error_details=error_details,
        )

    # ------------------------------------------------------------------
    # Deletion handler
    # ------------------------------------------------------------------

    def delete(self, document_id: UUID) -> DeletionResult:
        """Delete a document from storage and the search index.

        Args:
            document_id: Document to delete

        Returns:
            DeletionResult describing what was removed
        """
        self.logger.info("Deleting document", document_id=str(document_id))
        result = self._deletion_service.delete(document_id)

        # Invalidate cache
        self.document_cache.delete(document_id)

        return result

    # ------------------------------------------------------------------
    # Internal: storage monitor callback
    # ------------------------------------------------------------------

    def _safe_get_url(self, document_id) -> str:
        """Get storage URL without raising if document not found."""
        try:
            return self.storage.get_url(document_id)
        except Exception:
            return f"storage://{document_id}"

    def _on_upload_event(self, event) -> None:
        """Handle upload events from the storage monitor.

        Retrieves the document from cache/status manager and runs the
        processing pipeline.  Errors are logged and the document status
        is updated to FAILED.
        """
        document_id = event.document_id

        # Retrieve document from cache or reconstruct from event
        document = self.document_cache.get(document_id)
        if document is None:
            # Reconstruct minimal document from event payload
            document = Document(
                id=document_id,
                filename=event.filename,
                storageUrl=event.storage_url,
                contentType=event.content_type,
                status=DocumentStatus.UPLOADED,
                ownerId=event.owner_id,
            )

        try:
            self._processor.process_document(document)
            # processor already set status to INDEXED on the document object.
            # Sync it to the status manager without re-validating.
            try:
                self.status_manager.transition(
                    document_id, DocumentStatus.INDEXED, validate=False
                )
            except Exception:
                pass  # status manager may already reflect INDEXED
            # Update cache with new status
            self.document_cache.set(document)

        except Exception as e:
            self.error_logger.log_error(document_id, e, stage="processing")
            # Ensure status is FAILED
            try:
                self.status_manager.transition(
                    document_id, DocumentStatus.FAILED, validate=False
                )
            except Exception:
                pass
            # Enqueue for retry if it's an indexing failure
            if "indexing" in str(e).lower():
                self.retry_queue.enqueue(document_id, operation="index", error=str(e))

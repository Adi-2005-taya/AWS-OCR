"""Status management layer for DocuSense System

Handles status persistence, change event logging, and index timestamp
recording for documents.

Requirements: 4.2, 6.2
"""

import structlog
from datetime import UTC, datetime
from typing import Callable, Dict, List, Optional
from uuid import UUID

from src.constants import DocumentStatus
from src.exceptions import DocumentNotFoundError, InvalidDocumentStatusError
from src.models import Document

logger = structlog.get_logger(__name__)

# Valid status transitions
_VALID_TRANSITIONS: Dict[DocumentStatus, List[DocumentStatus]] = {
    DocumentStatus.UPLOADED: [DocumentStatus.PROCESSING, DocumentStatus.FAILED],
    DocumentStatus.PROCESSING: [DocumentStatus.INDEXED, DocumentStatus.FAILED],
    DocumentStatus.INDEXED: [],          # terminal state
    DocumentStatus.FAILED: [DocumentStatus.UPLOADED],  # allow re-upload/retry
}


class StatusChangeEvent:
    """Represents a document status change event.

    Attributes:
        document_id: Document whose status changed
        old_status: Previous status
        new_status: New status
        timestamp: When the change occurred
    """

    def __init__(
        self,
        document_id: UUID,
        old_status: Optional[DocumentStatus],
        new_status: DocumentStatus,
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.document_id = document_id
        self.old_status = old_status
        self.new_status = new_status
        self.timestamp = timestamp or datetime.now(UTC)


class StatusManager:
    """Manages document status persistence and change tracking.

    Provides an in-memory status store with event logging and
    index timestamp recording.

    Requirements: 4.2, 6.2
    """

    def __init__(self) -> None:
        """Initialize the status manager."""
        self._statuses: Dict[UUID, DocumentStatus] = {}
        self._index_timestamps: Dict[UUID, datetime] = {}
        self._change_log: List[StatusChangeEvent] = []
        self._change_callbacks: List[Callable[[StatusChangeEvent], None]] = []
        self.logger = logger.bind(component="status_manager")

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, document: Document) -> None:
        """Register a document and persist its initial status.

        Args:
            document: Document to register
        """
        self._statuses[document.id] = document.status
        self.logger.info(
            "Document registered",
            document_id=str(document.id),
            status=document.status,
        )

    # ------------------------------------------------------------------
    # Status retrieval
    # ------------------------------------------------------------------

    def get_status(self, document_id: UUID) -> DocumentStatus:
        """Get the current persisted status of a document.

        Args:
            document_id: Document identifier

        Returns:
            Current DocumentStatus

        Raises:
            DocumentNotFoundError: If document is not registered
        """
        if document_id not in self._statuses:
            raise DocumentNotFoundError(
                f"Document {document_id} not found in status manager",
                error_code="DOCUMENT_NOT_FOUND",
                details={"document_id": str(document_id)},
            )
        return self._statuses[document_id]

    def get_index_timestamp(self, document_id: UUID) -> Optional[datetime]:
        """Get the index timestamp for a document.

        Args:
            document_id: Document identifier

        Returns:
            Index timestamp, or None if not yet indexed
        """
        return self._index_timestamps.get(document_id)

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def transition(
        self,
        document_id: UUID,
        new_status: DocumentStatus,
        validate: bool = True,
    ) -> StatusChangeEvent:
        """Transition a document to a new status.

        Persists the new status, logs the change event, and records
        the index timestamp when transitioning to INDEXED.

        Args:
            document_id: Document to update
            new_status: Target status
            validate: Whether to validate the transition is allowed

        Returns:
            StatusChangeEvent describing the change

        Raises:
            DocumentNotFoundError: If document is not registered
            InvalidDocumentStatusError: If transition is not allowed
        """
        old_status = self.get_status(document_id)  # raises if not found

        if validate:
            allowed = _VALID_TRANSITIONS.get(old_status, [])
            if new_status not in allowed:
                raise InvalidDocumentStatusError(
                    f"Cannot transition from {old_status} to {new_status}",
                    error_code="INVALID_TRANSITION",
                    details={
                        "document_id": str(document_id),
                        "from_status": old_status,
                        "to_status": new_status,
                        "allowed": [s.value for s in allowed],
                    },
                )

        self._statuses[document_id] = new_status

        # Record index timestamp when document becomes INDEXED
        if new_status == DocumentStatus.INDEXED:
            self._index_timestamps[document_id] = datetime.now(UTC)

        event = StatusChangeEvent(
            document_id=document_id,
            old_status=old_status,
            new_status=new_status,
        )
        self._change_log.append(event)

        self.logger.info(
            "Document status changed",
            document_id=str(document_id),
            old_status=old_status,
            new_status=new_status,
        )

        for callback in self._change_callbacks:
            try:
                callback(event)
            except Exception as e:
                self.logger.error("Status change callback failed", error=str(e))

        return event

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def get_change_log(self, document_id: Optional[UUID] = None) -> List[StatusChangeEvent]:
        """Get the status change log.

        Args:
            document_id: Filter by document (returns all if None)

        Returns:
            List of StatusChangeEvent objects
        """
        if document_id is None:
            return list(self._change_log)
        return [e for e in self._change_log if e.document_id == document_id]

    def register_change_callback(
        self, callback: Callable[[StatusChangeEvent], None]
    ) -> None:
        """Register a callback invoked on every status change.

        Args:
            callback: Function accepting a StatusChangeEvent
        """
        self._change_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_registered(self, document_id: UUID) -> bool:
        """Check whether a document is registered.

        Args:
            document_id: Document identifier

        Returns:
            True if registered
        """
        return document_id in self._statuses


# Global instance
_status_manager: Optional[StatusManager] = None


def get_status_manager() -> StatusManager:
    """Get the global StatusManager singleton."""
    global _status_manager
    if _status_manager is None:
        _status_manager = StatusManager()
    return _status_manager


def reset_status_manager() -> None:
    """Reset the global StatusManager (for testing)."""
    global _status_manager
    _status_manager = None

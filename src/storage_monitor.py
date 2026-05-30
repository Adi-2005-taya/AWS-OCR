"""Storage Monitor for DocuSense System

This module provides an event-driven storage monitor that detects new file uploads
and triggers the Document Processor. It implements an event listener pattern with
handler registration for upload events.

Requirements: 2.1, 2.2
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from src.exceptions import OCRSystemError

logger = logging.getLogger(__name__)


class StorageMonitorError(OCRSystemError):
    """Base exception for storage monitor errors."""
    pass


class InvalidEventError(StorageMonitorError):
    """Raised when an event payload is invalid."""
    pass


@dataclass
class UploadEvent:
    """Upload event data structure.
    
    Represents a file upload event detected by the storage monitor.
    
    Attributes:
        document_id: Unique identifier of the uploaded document
        filename: Original filename of the uploaded document
        storage_url: Storage location URL
        content_type: MIME type of the uploaded file
        upload_timestamp: Timestamp when the upload occurred
        metadata: Additional event metadata
    """
    
    document_id: UUID
    filename: str
    storage_url: str
    content_type: str
    upload_timestamp: datetime
    metadata: Dict[str, Any]
    owner_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation.
        
        Returns:
            Dictionary representation of the event
        """
        return {
            "document_id": str(self.document_id),
            "filename": self.filename,
            "storage_url": self.storage_url,
            "content_type": self.content_type,
            "upload_timestamp": self.upload_timestamp.isoformat(),
            "metadata": self.metadata,
            "owner_id": self.owner_id,
        }


# Type alias for event handler functions
EventHandler = Callable[[UploadEvent], None]


class EventPayloadParser:
    """Parser for upload event payloads.
    
    This class handles parsing and validation of raw event data into
    structured UploadEvent objects.
    """
    
    @staticmethod
    def parse(payload: Dict[str, Any]) -> UploadEvent:
        """Parse a raw event payload into an UploadEvent.
        
        Args:
            payload: Raw event data dictionary
            
        Returns:
            Parsed UploadEvent object
            
        Raises:
            InvalidEventError: If the payload is invalid or missing required fields
        """
        try:
            # Extract required fields
            document_id = payload.get("document_id")
            filename = payload.get("filename")
            storage_url = payload.get("storage_url")
            content_type = payload.get("content_type")
            upload_timestamp = payload.get("upload_timestamp")
            owner_id = payload.get("owner_id")
            
            # Validate required fields
            if not document_id:
                raise InvalidEventError(
                    "Missing required field: document_id",
                    error_code="MISSING_DOCUMENT_ID",
                    details={"payload": payload}
                )
            
            if not filename:
                raise InvalidEventError(
                    "Missing required field: filename",
                    error_code="MISSING_FILENAME",
                    details={"payload": payload}
                )
            
            if not storage_url:
                raise InvalidEventError(
                    "Missing required field: storage_url",
                    error_code="MISSING_STORAGE_URL",
                    details={"payload": payload}
                )
            
            if not content_type:
                raise InvalidEventError(
                    "Missing required field: content_type",
                    error_code="MISSING_CONTENT_TYPE",
                    details={"payload": payload}
                )
            
            # Parse document_id as UUID
            try:
                if isinstance(document_id, str):
                    document_id = UUID(document_id)
                elif not isinstance(document_id, UUID):
                    raise ValueError(f"Invalid document_id type: {type(document_id)}")
            except (ValueError, AttributeError) as e:
                raise InvalidEventError(
                    f"Invalid document_id format: {document_id}",
                    error_code="INVALID_DOCUMENT_ID",
                    details={"document_id": str(document_id), "error": str(e)}
                ) from e
            
            # Parse upload_timestamp
            if upload_timestamp is None:
                from datetime import UTC
                upload_timestamp = datetime.now(UTC)
            elif isinstance(upload_timestamp, str):
                try:
                    upload_timestamp = datetime.fromisoformat(upload_timestamp)
                except ValueError as e:
                    raise InvalidEventError(
                        f"Invalid upload_timestamp format: {upload_timestamp}",
                        error_code="INVALID_TIMESTAMP",
                        details={"upload_timestamp": upload_timestamp, "error": str(e)}
                    ) from e
            elif not isinstance(upload_timestamp, datetime):
                raise InvalidEventError(
                    f"Invalid upload_timestamp type: {type(upload_timestamp)}",
                    error_code="INVALID_TIMESTAMP_TYPE",
                    details={"upload_timestamp": str(upload_timestamp)}
                )
            
            # Extract metadata (optional)
            metadata = payload.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            
            # Create and return UploadEvent
            return UploadEvent(
                document_id=document_id,
                filename=filename,
                storage_url=storage_url,
                content_type=content_type,
                upload_timestamp=upload_timestamp,
                metadata=metadata,
                owner_id=owner_id,
            )
            
        except InvalidEventError:
            raise
        except Exception as e:
            raise InvalidEventError(
                f"Failed to parse event payload: {str(e)}",
                error_code="PARSE_ERROR",
                details={"payload": payload, "error": str(e)}
            ) from e
    
    @staticmethod
    def validate(payload: Dict[str, Any]) -> bool:
        """Validate an event payload without parsing.
        
        Args:
            payload: Raw event data dictionary
            
        Returns:
            True if the payload is valid, False otherwise
        """
        try:
            EventPayloadParser.parse(payload)
            return True
        except InvalidEventError:
            return False


class StorageMonitorInterface(ABC):
    """Abstract interface for storage monitors.
    
    This interface defines the contract for storage monitor implementations,
    ensuring consistent behavior across different storage backends.
    """
    
    @abstractmethod
    def register_handler(self, handler: EventHandler) -> None:
        """Register an event handler for upload events.
        
        Args:
            handler: Callable that will be invoked when an upload event occurs
        """
        pass
    
    @abstractmethod
    def unregister_handler(self, handler: EventHandler) -> bool:
        """Unregister an event handler.
        
        Args:
            handler: Handler to unregister
            
        Returns:
            True if handler was found and removed, False otherwise
        """
        pass
    
    @abstractmethod
    def on_file_uploaded(self, event: UploadEvent) -> None:
        """Handle a file upload event.
        
        This method is called when a new file is uploaded to storage.
        It invokes all registered event handlers.
        
        Args:
            event: Upload event data
        """
        pass
    
    @abstractmethod
    def start(self) -> None:
        """Start monitoring for upload events."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop monitoring for upload events."""
        pass


class StorageMonitor(StorageMonitorInterface):
    """Event-driven storage monitor implementation.
    
    This monitor detects new file uploads and invokes registered handlers
    to trigger document processing. It supports multiple event handlers
    and provides error handling for handler failures.
    
    Attributes:
        _handlers: List of registered event handlers
        _is_running: Flag indicating if the monitor is active
        _parser: Event payload parser instance
    """
    
    def __init__(self) -> None:
        """Initialize the storage monitor."""
        self._handlers: List[EventHandler] = []
        self._is_running: bool = False
        self._parser = EventPayloadParser()
        logger.info("Storage monitor initialized")
    
    def register_handler(self, handler: EventHandler) -> None:
        """Register an event handler for upload events.
        
        Args:
            handler: Callable that will be invoked when an upload event occurs
            
        Raises:
            ValueError: If handler is not callable
        """
        if not callable(handler):
            raise ValueError("Handler must be callable")
        
        if handler not in self._handlers:
            self._handlers.append(handler)
            logger.info(f"Registered event handler: {handler.__name__}")
        else:
            logger.warning(f"Handler already registered: {handler.__name__}")
    
    def unregister_handler(self, handler: EventHandler) -> bool:
        """Unregister an event handler.
        
        Args:
            handler: Handler to unregister
            
        Returns:
            True if handler was found and removed, False otherwise
        """
        try:
            self._handlers.remove(handler)
            logger.info(f"Unregistered event handler: {handler.__name__}")
            return True
        except ValueError:
            logger.warning(f"Handler not found: {handler.__name__}")
            return False
    
    def on_file_uploaded(self, event: UploadEvent) -> None:
        """Handle a file upload event.
        
        This method is called when a new file is uploaded to storage.
        It invokes all registered event handlers in order of registration.
        
        Args:
            event: Upload event data
            
        Raises:
            StorageMonitorError: If no handlers are registered
        """
        if not self._is_running:
            logger.warning("Storage monitor is not running, ignoring event")
            return
        
        if not self._handlers:
            logger.warning("No handlers registered for upload event")
            return
        
        logger.info(
            f"Processing upload event for document {event.document_id} "
            f"(filename: {event.filename})"
        )
        
        # Invoke all registered handlers
        for handler in self._handlers:
            try:
                logger.debug(f"Invoking handler: {handler.__name__}")
                handler(event)
                logger.debug(f"Handler completed: {handler.__name__}")
            except Exception as e:
                # Log handler errors but continue processing other handlers
                logger.error(
                    f"Handler {handler.__name__} failed for document "
                    f"{event.document_id}: {str(e)}",
                    exc_info=True
                )
    
    def trigger_event(self, payload: Dict[str, Any]) -> None:
        """Trigger an upload event from a raw payload.
        
        This is a convenience method that parses the payload and invokes
        the event handler.
        
        Args:
            payload: Raw event data dictionary
            
        Raises:
            InvalidEventError: If the payload is invalid
        """
        event = self._parser.parse(payload)
        self.on_file_uploaded(event)
    
    def start(self) -> None:
        """Start monitoring for upload events."""
        if self._is_running:
            logger.warning("Storage monitor is already running")
            return
        
        self._is_running = True
        logger.info("Storage monitor started")
    
    def stop(self) -> None:
        """Stop monitoring for upload events."""
        if not self._is_running:
            logger.warning("Storage monitor is not running")
            return
        
        self._is_running = False
        logger.info("Storage monitor stopped")
    
    def is_running(self) -> bool:
        """Check if the monitor is currently running.
        
        Returns:
            True if the monitor is running, False otherwise
        """
        return self._is_running
    
    def get_handler_count(self) -> int:
        """Get the number of registered handlers.
        
        Returns:
            Number of registered event handlers
        """
        return len(self._handlers)


class StorageMonitorFactory:
    """Factory for creating storage monitor instances."""
    
    @staticmethod
    def create_monitor() -> StorageMonitorInterface:
        """Create a storage monitor instance.
        
        Returns:
            Storage monitor implementation
        """
        return StorageMonitor()

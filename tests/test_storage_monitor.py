"""Unit tests for Storage Monitor component

Tests cover:
- Event payload parsing and validation
- Event handler registration and invocation
- Error handling for invalid events and handler failures
- Monitor lifecycle (start/stop)

Requirements: 2.1, 2.2
"""

import pytest
from datetime import datetime, UTC
from uuid import UUID, uuid4
from typing import Dict, Any, List

from src.storage_monitor import (
    StorageMonitor,
    StorageMonitorFactory,
    UploadEvent,
    EventPayloadParser,
    InvalidEventError,
    StorageMonitorError,
)


class TestUploadEvent:
    """Tests for UploadEvent data structure."""
    
    def test_upload_event_creation(self):
        """Test creating an UploadEvent with all fields."""
        doc_id = uuid4()
        timestamp = datetime.now(UTC)
        
        event = UploadEvent(
            document_id=doc_id,
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=timestamp,
            metadata={"size": 1024, "user": "test_user"}
        )
        
        assert event.document_id == doc_id
        assert event.filename == "test.pdf"
        assert event.storage_url == "file:///path/to/test.pdf"
        assert event.content_type == "application/pdf"
        assert event.upload_timestamp == timestamp
        assert event.metadata == {"size": 1024, "user": "test_user"}
    
    def test_upload_event_to_dict(self):
        """Test converting UploadEvent to dictionary."""
        doc_id = uuid4()
        timestamp = datetime.now(UTC)
        
        event = UploadEvent(
            document_id=doc_id,
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=timestamp,
            metadata={"size": 1024}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["document_id"] == str(doc_id)
        assert event_dict["filename"] == "test.pdf"
        assert event_dict["storage_url"] == "file:///path/to/test.pdf"
        assert event_dict["content_type"] == "application/pdf"
        assert event_dict["upload_timestamp"] == timestamp.isoformat()
        assert event_dict["metadata"] == {"size": 1024}


class TestEventPayloadParser:
    """Tests for EventPayloadParser."""
    
    def test_parse_valid_payload(self):
        """Test parsing a valid event payload."""
        doc_id = uuid4()
        timestamp = datetime.now(UTC)
        
        payload = {
            "document_id": str(doc_id),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
            "upload_timestamp": timestamp.isoformat(),
            "metadata": {"size": 1024}
        }
        
        event = EventPayloadParser.parse(payload)
        
        assert event.document_id == doc_id
        assert event.filename == "test.pdf"
        assert event.storage_url == "file:///path/to/test.pdf"
        assert event.content_type == "application/pdf"
        assert event.metadata == {"size": 1024}
    
    def test_parse_payload_with_uuid_object(self):
        """Test parsing payload with UUID object instead of string."""
        doc_id = uuid4()
        
        payload = {
            "document_id": doc_id,
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        event = EventPayloadParser.parse(payload)
        
        assert event.document_id == doc_id
    
    def test_parse_payload_without_timestamp(self):
        """Test parsing payload without timestamp (should use current time)."""
        doc_id = uuid4()
        
        payload = {
            "document_id": str(doc_id),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        before = datetime.now(UTC)
        event = EventPayloadParser.parse(payload)
        after = datetime.now(UTC)
        
        assert before <= event.upload_timestamp <= after
    
    def test_parse_payload_without_metadata(self):
        """Test parsing payload without metadata (should default to empty dict)."""
        doc_id = uuid4()
        
        payload = {
            "document_id": str(doc_id),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        event = EventPayloadParser.parse(payload)
        
        assert event.metadata == {}
    
    def test_parse_payload_with_invalid_metadata(self):
        """Test parsing payload with non-dict metadata (should default to empty dict)."""
        doc_id = uuid4()
        
        payload = {
            "document_id": str(doc_id),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
            "metadata": "invalid"
        }
        
        event = EventPayloadParser.parse(payload)
        
        assert event.metadata == {}
    
    def test_parse_missing_document_id(self):
        """Test parsing payload with missing document_id."""
        payload = {
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        with pytest.raises(InvalidEventError) as exc_info:
            EventPayloadParser.parse(payload)
        
        assert "document_id" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "MISSING_DOCUMENT_ID"
    
    def test_parse_missing_filename(self):
        """Test parsing payload with missing filename."""
        payload = {
            "document_id": str(uuid4()),
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        with pytest.raises(InvalidEventError) as exc_info:
            EventPayloadParser.parse(payload)
        
        assert "filename" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "MISSING_FILENAME"
    
    def test_parse_missing_storage_url(self):
        """Test parsing payload with missing storage_url."""
        payload = {
            "document_id": str(uuid4()),
            "filename": "test.pdf",
            "content_type": "application/pdf",
        }
        
        with pytest.raises(InvalidEventError) as exc_info:
            EventPayloadParser.parse(payload)
        
        assert "storage_url" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "MISSING_STORAGE_URL"
    
    def test_parse_missing_content_type(self):
        """Test parsing payload with missing content_type."""
        payload = {
            "document_id": str(uuid4()),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
        }
        
        with pytest.raises(InvalidEventError) as exc_info:
            EventPayloadParser.parse(payload)
        
        assert "content_type" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "MISSING_CONTENT_TYPE"
    
    def test_parse_invalid_document_id_format(self):
        """Test parsing payload with invalid document_id format."""
        payload = {
            "document_id": "not-a-uuid",
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        with pytest.raises(InvalidEventError) as exc_info:
            EventPayloadParser.parse(payload)
        
        assert "document_id" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "INVALID_DOCUMENT_ID"
    
    def test_parse_invalid_timestamp_format(self):
        """Test parsing payload with invalid timestamp format."""
        payload = {
            "document_id": str(uuid4()),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
            "upload_timestamp": "not-a-timestamp"
        }
        
        with pytest.raises(InvalidEventError) as exc_info:
            EventPayloadParser.parse(payload)
        
        assert "timestamp" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "INVALID_TIMESTAMP"
    
    def test_validate_valid_payload(self):
        """Test validating a valid payload."""
        payload = {
            "document_id": str(uuid4()),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        assert EventPayloadParser.validate(payload) is True
    
    def test_validate_invalid_payload(self):
        """Test validating an invalid payload."""
        payload = {
            "filename": "test.pdf",
            # Missing required fields
        }
        
        assert EventPayloadParser.validate(payload) is False


class TestStorageMonitor:
    """Tests for StorageMonitor implementation."""
    
    def test_monitor_initialization(self):
        """Test creating a storage monitor."""
        monitor = StorageMonitor()
        
        assert monitor.is_running() is False
        assert monitor.get_handler_count() == 0
    
    def test_start_monitor(self):
        """Test starting the monitor."""
        monitor = StorageMonitor()
        
        monitor.start()
        
        assert monitor.is_running() is True
    
    def test_stop_monitor(self):
        """Test stopping the monitor."""
        monitor = StorageMonitor()
        monitor.start()
        
        monitor.stop()
        
        assert monitor.is_running() is False
    
    def test_start_already_running_monitor(self):
        """Test starting a monitor that is already running."""
        monitor = StorageMonitor()
        monitor.start()
        
        # Should not raise an error
        monitor.start()
        
        assert monitor.is_running() is True
    
    def test_stop_not_running_monitor(self):
        """Test stopping a monitor that is not running."""
        monitor = StorageMonitor()
        
        # Should not raise an error
        monitor.stop()
        
        assert monitor.is_running() is False
    
    def test_register_handler(self):
        """Test registering an event handler."""
        monitor = StorageMonitor()
        
        def handler(event: UploadEvent) -> None:
            pass
        
        monitor.register_handler(handler)
        
        assert monitor.get_handler_count() == 1
    
    def test_register_multiple_handlers(self):
        """Test registering multiple event handlers."""
        monitor = StorageMonitor()
        
        def handler1(event: UploadEvent) -> None:
            pass
        
        def handler2(event: UploadEvent) -> None:
            pass
        
        monitor.register_handler(handler1)
        monitor.register_handler(handler2)
        
        assert monitor.get_handler_count() == 2
    
    def test_register_duplicate_handler(self):
        """Test registering the same handler twice (should not duplicate)."""
        monitor = StorageMonitor()
        
        def handler(event: UploadEvent) -> None:
            pass
        
        monitor.register_handler(handler)
        monitor.register_handler(handler)
        
        assert monitor.get_handler_count() == 1
    
    def test_register_non_callable_handler(self):
        """Test registering a non-callable handler."""
        monitor = StorageMonitor()
        
        with pytest.raises(ValueError) as exc_info:
            monitor.register_handler("not-callable")
        
        assert "callable" in str(exc_info.value).lower()
    
    def test_unregister_handler(self):
        """Test unregistering an event handler."""
        monitor = StorageMonitor()
        
        def handler(event: UploadEvent) -> None:
            pass
        
        monitor.register_handler(handler)
        result = monitor.unregister_handler(handler)
        
        assert result is True
        assert monitor.get_handler_count() == 0
    
    def test_unregister_nonexistent_handler(self):
        """Test unregistering a handler that was not registered."""
        monitor = StorageMonitor()
        
        def handler(event: UploadEvent) -> None:
            pass
        
        result = monitor.unregister_handler(handler)
        
        assert result is False
    
    def test_on_file_uploaded_invokes_handler(self):
        """Test that on_file_uploaded invokes registered handlers."""
        monitor = StorageMonitor()
        monitor.start()
        
        invoked = []
        
        def handler(event: UploadEvent) -> None:
            invoked.append(event)
        
        monitor.register_handler(handler)
        
        event = UploadEvent(
            document_id=uuid4(),
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={}
        )
        
        monitor.on_file_uploaded(event)
        
        assert len(invoked) == 1
        assert invoked[0] == event
    
    def test_on_file_uploaded_invokes_multiple_handlers(self):
        """Test that on_file_uploaded invokes all registered handlers."""
        monitor = StorageMonitor()
        monitor.start()
        
        invoked1 = []
        invoked2 = []
        
        def handler1(event: UploadEvent) -> None:
            invoked1.append(event)
        
        def handler2(event: UploadEvent) -> None:
            invoked2.append(event)
        
        monitor.register_handler(handler1)
        monitor.register_handler(handler2)
        
        event = UploadEvent(
            document_id=uuid4(),
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={}
        )
        
        monitor.on_file_uploaded(event)
        
        assert len(invoked1) == 1
        assert len(invoked2) == 1
        assert invoked1[0] == event
        assert invoked2[0] == event
    
    def test_on_file_uploaded_when_not_running(self):
        """Test that on_file_uploaded does nothing when monitor is not running."""
        monitor = StorageMonitor()
        # Don't start the monitor
        
        invoked = []
        
        def handler(event: UploadEvent) -> None:
            invoked.append(event)
        
        monitor.register_handler(handler)
        
        event = UploadEvent(
            document_id=uuid4(),
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={}
        )
        
        monitor.on_file_uploaded(event)
        
        # Handler should not be invoked
        assert len(invoked) == 0
    
    def test_on_file_uploaded_with_no_handlers(self):
        """Test that on_file_uploaded handles case with no registered handlers."""
        monitor = StorageMonitor()
        monitor.start()
        
        event = UploadEvent(
            document_id=uuid4(),
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={}
        )
        
        # Should not raise an error
        monitor.on_file_uploaded(event)
    
    def test_on_file_uploaded_handler_error_continues_processing(self):
        """Test that handler errors don't stop other handlers from executing."""
        monitor = StorageMonitor()
        monitor.start()
        
        invoked = []
        
        def failing_handler(event: UploadEvent) -> None:
            raise RuntimeError("Handler failed")
        
        def successful_handler(event: UploadEvent) -> None:
            invoked.append(event)
        
        monitor.register_handler(failing_handler)
        monitor.register_handler(successful_handler)
        
        event = UploadEvent(
            document_id=uuid4(),
            filename="test.pdf",
            storage_url="file:///path/to/test.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={}
        )
        
        # Should not raise an error
        monitor.on_file_uploaded(event)
        
        # Successful handler should still be invoked
        assert len(invoked) == 1
    
    def test_trigger_event_with_valid_payload(self):
        """Test triggering an event from a raw payload."""
        monitor = StorageMonitor()
        monitor.start()
        
        invoked = []
        
        def handler(event: UploadEvent) -> None:
            invoked.append(event)
        
        monitor.register_handler(handler)
        
        doc_id = uuid4()
        payload = {
            "document_id": str(doc_id),
            "filename": "test.pdf",
            "storage_url": "file:///path/to/test.pdf",
            "content_type": "application/pdf",
        }
        
        monitor.trigger_event(payload)
        
        assert len(invoked) == 1
        assert invoked[0].document_id == doc_id
        assert invoked[0].filename == "test.pdf"
    
    def test_trigger_event_with_invalid_payload(self):
        """Test triggering an event with invalid payload raises error."""
        monitor = StorageMonitor()
        monitor.start()
        
        payload = {
            "filename": "test.pdf",
            # Missing required fields
        }
        
        with pytest.raises(InvalidEventError):
            monitor.trigger_event(payload)


class TestStorageMonitorFactory:
    """Tests for StorageMonitorFactory."""
    
    def test_create_monitor(self):
        """Test creating a monitor using the factory."""
        monitor = StorageMonitorFactory.create_monitor()
        
        assert monitor is not None
        assert isinstance(monitor, StorageMonitor)
        assert monitor.is_running() is False
        assert monitor.get_handler_count() == 0


class TestStorageMonitorIntegration:
    """Integration tests for storage monitor with realistic scenarios."""
    
    def test_complete_upload_workflow(self):
        """Test complete workflow: register handler, start monitor, trigger event."""
        monitor = StorageMonitor()
        
        # Track processed documents
        processed_documents = []
        
        def document_processor(event: UploadEvent) -> None:
            """Simulated document processor handler."""
            processed_documents.append({
                "document_id": event.document_id,
                "filename": event.filename,
                "content_type": event.content_type,
            })
        
        # Register handler
        monitor.register_handler(document_processor)
        
        # Start monitor
        monitor.start()
        
        # Simulate upload events
        doc_id1 = uuid4()
        doc_id2 = uuid4()
        
        event1 = UploadEvent(
            document_id=doc_id1,
            filename="invoice.pdf",
            storage_url="file:///path/to/invoice.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={"user": "alice"}
        )
        
        event2 = UploadEvent(
            document_id=doc_id2,
            filename="receipt.png",
            storage_url="file:///path/to/receipt.png",
            content_type="image/png",
            upload_timestamp=datetime.now(UTC),
            metadata={"user": "bob"}
        )
        
        monitor.on_file_uploaded(event1)
        monitor.on_file_uploaded(event2)
        
        # Verify both documents were processed
        assert len(processed_documents) == 2
        assert processed_documents[0]["document_id"] == doc_id1
        assert processed_documents[0]["filename"] == "invoice.pdf"
        assert processed_documents[1]["document_id"] == doc_id2
        assert processed_documents[1]["filename"] == "receipt.png"
        
        # Stop monitor
        monitor.stop()
        assert monitor.is_running() is False
    
    def test_multiple_handlers_workflow(self):
        """Test workflow with multiple handlers for different purposes."""
        monitor = StorageMonitor()
        
        # Track different aspects
        logged_events = []
        processed_documents = []
        
        def logger_handler(event: UploadEvent) -> None:
            """Log upload events."""
            logged_events.append(f"Uploaded: {event.filename}")
        
        def processor_handler(event: UploadEvent) -> None:
            """Process documents."""
            processed_documents.append(event.document_id)
        
        # Register multiple handlers
        monitor.register_handler(logger_handler)
        monitor.register_handler(processor_handler)
        
        monitor.start()
        
        # Trigger event
        event = UploadEvent(
            document_id=uuid4(),
            filename="document.pdf",
            storage_url="file:///path/to/document.pdf",
            content_type="application/pdf",
            upload_timestamp=datetime.now(UTC),
            metadata={}
        )
        
        monitor.on_file_uploaded(event)
        
        # Verify both handlers were invoked
        assert len(logged_events) == 1
        assert "document.pdf" in logged_events[0]
        assert len(processed_documents) == 1

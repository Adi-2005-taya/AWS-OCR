"""Unit tests for document processor

Tests cover:
- Document processing pipeline orchestration
- Status validation and transitions
- OCR service integration
- Text cleaning integration
- Search indexing integration
- Error handling for each stage

Requirements: 2.3, 2.4, 2.6, 4.3, 6.2, 6.3
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from src.constants import DocumentStatus
from src.document_processor import DocumentProcessor, create_document_processor
from src.exceptions import (
    DocumentProcessingError,
    InvalidDocumentStatusError
)
from src.models import Document, IndexedDocument, OCRResult


class MockStorage:
    """Mock storage for testing"""
    
    def __init__(self):
        self.documents = {}
    
    def download(self, document_id):
        """Mock download"""
        if document_id not in self.documents:
            raise Exception(f"Document {document_id} not found")
        return self.documents[document_id]
    
    def add_document(self, document_id, data):
        """Add document to mock storage"""
        self.documents[document_id] = data


class MockOCRService:
    """Mock OCR service for testing"""
    
    def __init__(self, should_fail=False, confidence=0.95):
        self.should_fail = should_fail
        self.confidence = confidence
        self.calls = []
    
    def extract_text(self, document_data, content_type):
        """Mock extract text"""
        self.calls.append((document_data, content_type))
        
        if self.should_fail:
            raise Exception("OCR extraction failed")
        
        return OCRResult(
            documentId=uuid4(),
            rawText="Test  invoice\n\nAmount: $100",
            confidence=self.confidence,
            processingTime=1.5,
            metadata={"engine": "mock"}
        )


class MockTextCleaner:
    """Mock text cleaner for testing"""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.clean_calls = []
        self.keyword_calls = []
    
    def clean(self, text):
        """Mock clean"""
        self.clean_calls.append(text)
        
        if self.should_fail:
            raise Exception("Text cleaning failed")
        
        return "test invoice amount $100"
    
    def extract_keywords(self, text):
        """Mock extract keywords"""
        self.keyword_calls.append(text)
        return ["test", "invoice", "amount"]


class MockSearchEngine:
    """Mock search engine for testing"""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.indexed_documents = []
    
    def index(self, document):
        """Mock index"""
        if self.should_fail:
            raise Exception("Indexing failed")
        
        self.indexed_documents.append(document)


class TestDocumentProcessor:
    """Tests for DocumentProcessor class."""
    
    def test_processor_initialization(self):
        """Test document processor can be initialized with custom components."""
        # Use mock components to avoid Tesseract dependency
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        assert processor is not None
        assert processor.storage is not None
        assert processor.ocr_service is not None
        assert processor.text_cleaner is not None
        assert processor.search_engine is not None
    
    def test_processor_initialization_with_custom_components(self):
        """Test processor initialization with custom components."""
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        assert processor.storage is storage
        assert processor.ocr_service is ocr_service
        assert processor.text_cleaner is text_cleaner
        assert processor.search_engine is search_engine
    
    def test_process_document_success(self):
        """Test successful document processing."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"fake image data")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        result = processor.process_document(document)
        
        # Verify result
        assert isinstance(result, IndexedDocument)
        assert result.documentId == doc_id
        assert len(result.cleanedText) > 0
        assert len(result.keywords) > 0
        
        # Verify status updated to INDEXED
        assert document.status == DocumentStatus.INDEXED
        
        # Verify OCR was called
        assert len(ocr_service.calls) == 1
        
        # Verify text cleaner was called
        assert len(text_cleaner.clean_calls) == 1
        assert len(text_cleaner.keyword_calls) == 1
        
        # Verify document was indexed
        assert len(search_engine.indexed_documents) == 1
    
    def test_process_document_invalid_status_raises_error(self):
        """Test that processing document with invalid status raises error."""
        doc_id = uuid4()
        
        # Use mock components
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.PROCESSING  # Invalid status
        )
        
        with pytest.raises(InvalidDocumentStatusError) as exc_info:
            processor.process_document(document)
        
        assert "UPLOADED" in str(exc_info.value)
        assert document.status == DocumentStatus.PROCESSING  # Status unchanged
    
    def test_process_document_status_transitions(self):
        """Test document status transitions during processing."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"fake image data")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        # Initial status
        assert document.status == DocumentStatus.UPLOADED
        
        # Process document
        processor.process_document(document)
        
        # Final status
        assert document.status == DocumentStatus.INDEXED
    
    def test_process_document_ocr_failure_updates_status_to_failed(self):
        """Test that OCR failure updates document status to FAILED."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"fake image data")
        
        ocr_service = MockOCRService(should_fail=True)
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        with pytest.raises(DocumentProcessingError) as exc_info:
            processor.process_document(document)
        
        assert "OCR extraction failed" in str(exc_info.value)
        assert document.status == DocumentStatus.FAILED
        
        # Verify text cleaner and search engine were not called
        assert len(text_cleaner.clean_calls) == 0
        assert len(search_engine.indexed_documents) == 0
    
    def test_process_document_text_cleaning_failure_updates_status_to_failed(self):
        """Test that text cleaning failure updates document status to FAILED."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"fake image data")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner(should_fail=True)
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        with pytest.raises(DocumentProcessingError) as exc_info:
            processor.process_document(document)
        
        assert "Text cleaning failed" in str(exc_info.value)
        assert document.status == DocumentStatus.FAILED
        
        # Verify OCR was called but search engine was not
        assert len(ocr_service.calls) == 1
        assert len(search_engine.indexed_documents) == 0
    
    def test_process_document_indexing_failure_updates_status_to_failed(self):
        """Test that indexing failure updates document status to FAILED."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"fake image data")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine(should_fail=True)
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        with pytest.raises(DocumentProcessingError) as exc_info:
            processor.process_document(document)
        
        assert "Document indexing failed" in str(exc_info.value)
        assert document.status == DocumentStatus.FAILED
        
        # Verify OCR and text cleaning were called
        assert len(ocr_service.calls) == 1
        assert len(text_cleaner.clean_calls) == 1
    
    def test_process_document_downloads_from_storage(self):
        """Test that document is downloaded from storage."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"test document data")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        processor.process_document(document)
        
        # Verify OCR service received the document data
        assert len(ocr_service.calls) == 1
        assert ocr_service.calls[0][0] == b"test document data"
        assert ocr_service.calls[0][1] == doc_id  # second arg is document_id
    
    def test_process_document_creates_indexed_document_with_correct_fields(self):
        """Test that indexed document has all required fields."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"fake image data")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        document = Document(
            id=doc_id,
            filename="test.pdf",
            storageUrl="file:///test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        result = processor.process_document(document)
        
        assert result.documentId == doc_id
        assert result.cleanedText == "test invoice amount $100"
        assert result.keywords == ["test", "invoice", "amount"]
        assert result.searchableContent == "test invoice amount $100"
        assert result.indexTimestamp is not None


class TestCreateDocumentProcessor:
    """Tests for create_document_processor factory function."""
    
    def test_create_document_processor(self):
        """Test creating document processor with factory function and custom components."""
        # Use mock components to avoid Tesseract dependency
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = create_document_processor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        assert isinstance(processor, DocumentProcessor)
    
    def test_create_document_processor_with_custom_components(self):
        """Test creating processor with custom components."""
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = create_document_processor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        assert processor.storage is storage
        assert processor.ocr_service is ocr_service
        assert processor.text_cleaner is text_cleaner
        assert processor.search_engine is search_engine


class TestDocumentProcessorIntegration:
    """Integration tests for document processor."""
    
    def test_complete_processing_workflow(self):
        """Test complete document processing workflow."""
        doc_id = uuid4()
        
        storage = MockStorage()
        storage.add_document(doc_id, b"Invoice\nDate: 2024-01-15\nAmount: $100.00")
        
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        # Create document
        document = Document(
            id=doc_id,
            filename="invoice.pdf",
            storageUrl="file:///invoice.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        # Process document
        result = processor.process_document(document)
        
        # Verify complete workflow
        assert document.status == DocumentStatus.INDEXED
        assert result.documentId == doc_id
        assert len(result.cleanedText) > 0
        assert len(result.keywords) > 0
        assert len(search_engine.indexed_documents) == 1
        assert search_engine.indexed_documents[0].documentId == doc_id
    
    def test_multiple_documents_processing(self):
        """Test processing multiple documents."""
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        # Process 3 documents
        for i in range(3):
            doc_id = uuid4()
            storage.add_document(doc_id, f"Document {i}".encode())
            
            document = Document(
                id=doc_id,
                filename=f"doc{i}.pdf",
                storageUrl=f"file:///doc{i}.pdf",
                contentType="application/pdf",
                status=DocumentStatus.UPLOADED
            )
            
            result = processor.process_document(document)
            
            assert document.status == DocumentStatus.INDEXED
            assert result.documentId == doc_id
        
        # Verify all documents were indexed
        assert len(search_engine.indexed_documents) == 3
    
    def test_error_recovery_allows_subsequent_processing(self):
        """Test that error in one document doesn't prevent processing others."""
        storage = MockStorage()
        ocr_service = MockOCRService()
        text_cleaner = MockTextCleaner()
        search_engine = MockSearchEngine()
        
        processor = DocumentProcessor(
            storage=storage,
            ocr_service=ocr_service,
            text_cleaner=text_cleaner,
            search_engine=search_engine
        )
        
        # First document - will fail (not in storage)
        doc1_id = uuid4()
        doc1 = Document(
            id=doc1_id,
            filename="doc1.pdf",
            storageUrl="file:///doc1.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        with pytest.raises(DocumentProcessingError):
            processor.process_document(doc1)
        
        assert doc1.status == DocumentStatus.FAILED
        
        # Second document - should succeed
        doc2_id = uuid4()
        storage.add_document(doc2_id, b"Document 2")
        
        doc2 = Document(
            id=doc2_id,
            filename="doc2.pdf",
            storageUrl="file:///doc2.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        result = processor.process_document(doc2)
        
        assert doc2.status == DocumentStatus.INDEXED
        assert result.documentId == doc2_id

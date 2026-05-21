"""Unit tests for data models

Tests the core data model classes: Document, OCRResult, and IndexedDocument.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.constants import DocumentStatus
from src.models import Document, IndexedDocument, OCRResult


class TestDocument:
    """Tests for the Document model"""
    
    def test_document_creation_with_all_fields(self):
        """Test creating a document with all required fields"""
        doc_id = uuid4()
        timestamp = datetime.now(UTC)
        
        doc = Document(
            id=doc_id,
            filename="test.pdf",
            uploadTimestamp=timestamp,
            storageUrl="s3://bucket/test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.UPLOADED
        )
        
        assert doc.id == doc_id
        assert doc.filename == "test.pdf"
        assert doc.uploadTimestamp == timestamp
        assert doc.storageUrl == "s3://bucket/test.pdf"
        assert doc.contentType == "application/pdf"
        assert doc.status == DocumentStatus.UPLOADED
    
    def test_document_creation_with_defaults(self):
        """Test creating a document with default values for optional fields"""
        doc = Document(
            filename="test.pdf",
            storageUrl="s3://bucket/test.pdf",
            contentType="application/pdf"
        )
        
        assert isinstance(doc.id, UUID)
        assert isinstance(doc.uploadTimestamp, datetime)
        assert doc.status == DocumentStatus.UPLOADED
    
    def test_document_status_transitions(self):
        """Test that document status can be updated through valid states"""
        doc = Document(
            filename="test.pdf",
            storageUrl="s3://bucket/test.pdf",
            contentType="application/pdf"
        )
        
        assert doc.status == DocumentStatus.UPLOADED
        
        doc.status = DocumentStatus.PROCESSING
        assert doc.status == DocumentStatus.PROCESSING
        
        doc.status = DocumentStatus.INDEXED
        assert doc.status == DocumentStatus.INDEXED
    
    def test_document_failed_status(self):
        """Test that document can be set to FAILED status"""
        doc = Document(
            filename="test.pdf",
            storageUrl="s3://bucket/test.pdf",
            contentType="application/pdf",
            status=DocumentStatus.PROCESSING
        )
        
        doc.status = DocumentStatus.FAILED
        assert doc.status == DocumentStatus.FAILED
    
    def test_document_missing_required_fields(self):
        """Test that creating a document without required fields raises error"""
        with pytest.raises(ValidationError):
            Document(filename="test.pdf")
    
    def test_document_serialization(self):
        """Test that document can be serialized to dict"""
        doc = Document(
            filename="test.pdf",
            storageUrl="s3://bucket/test.pdf",
            contentType="application/pdf"
        )
        
        doc_dict = doc.model_dump()
        assert doc_dict["filename"] == "test.pdf"
        assert doc_dict["storageUrl"] == "s3://bucket/test.pdf"
        assert doc_dict["contentType"] == "application/pdf"
        assert doc_dict["status"] == "UPLOADED"


class TestOCRResult:
    """Tests for the OCRResult model"""
    
    def test_ocr_result_creation(self):
        """Test creating an OCR result with all fields"""
        doc_id = uuid4()
        
        result = OCRResult(
            documentId=doc_id,
            rawText="Sample extracted text",
            confidence=0.95,
            processingTime=2.5,
            metadata={"engine": "tesseract", "language": "eng"}
        )
        
        assert result.documentId == doc_id
        assert result.rawText == "Sample extracted text"
        assert result.confidence == 0.95
        assert result.processingTime == 2.5
        assert result.metadata == {"engine": "tesseract", "language": "eng"}
    
    def test_ocr_result_with_empty_metadata(self):
        """Test creating an OCR result with default empty metadata"""
        doc_id = uuid4()
        
        result = OCRResult(
            documentId=doc_id,
            rawText="Sample text",
            confidence=0.85,
            processingTime=1.5
        )
        
        assert result.metadata == {}
    
    def test_ocr_result_confidence_validation(self):
        """Test that confidence must be between 0.0 and 1.0"""
        doc_id = uuid4()
        
        # Valid confidence values
        result = OCRResult(
            documentId=doc_id,
            rawText="text",
            confidence=0.0,
            processingTime=1.0
        )
        assert result.confidence == 0.0
        
        result = OCRResult(
            documentId=doc_id,
            rawText="text",
            confidence=1.0,
            processingTime=1.0
        )
        assert result.confidence == 1.0
        
        # Invalid confidence values
        with pytest.raises(ValidationError):
            OCRResult(
                documentId=doc_id,
                rawText="text",
                confidence=-0.1,
                processingTime=1.0
            )
        
        with pytest.raises(ValidationError):
            OCRResult(
                documentId=doc_id,
                rawText="text",
                confidence=1.1,
                processingTime=1.0
            )
    
    def test_ocr_result_processing_time_validation(self):
        """Test that processing time must be positive"""
        doc_id = uuid4()
        
        # Valid processing time
        result = OCRResult(
            documentId=doc_id,
            rawText="text",
            confidence=0.9,
            processingTime=0.1
        )
        assert result.processingTime == 0.1
        
        # Invalid processing time (zero)
        with pytest.raises(ValidationError):
            OCRResult(
                documentId=doc_id,
                rawText="text",
                confidence=0.9,
                processingTime=0.0
            )
        
        # Invalid processing time (negative)
        with pytest.raises(ValidationError):
            OCRResult(
                documentId=doc_id,
                rawText="text",
                confidence=0.9,
                processingTime=-1.0
            )
    
    def test_ocr_result_missing_required_fields(self):
        """Test that creating an OCR result without required fields raises error"""
        with pytest.raises(ValidationError):
            OCRResult(rawText="text", confidence=0.9)


class TestIndexedDocument:
    """Tests for the IndexedDocument model"""
    
    def test_indexed_document_creation(self):
        """Test creating an indexed document with all fields"""
        doc_id = uuid4()
        timestamp = datetime.now(UTC)
        
        indexed = IndexedDocument(
            documentId=doc_id,
            cleanedText="cleaned text content",
            keywords=["cleaned", "text", "content"],
            indexTimestamp=timestamp,
            searchableContent="cleaned text content"
        )
        
        assert indexed.documentId == doc_id
        assert indexed.cleanedText == "cleaned text content"
        assert indexed.keywords == ["cleaned", "text", "content"]
        assert indexed.indexTimestamp == timestamp
        assert indexed.searchableContent == "cleaned text content"
    
    def test_indexed_document_with_defaults(self):
        """Test creating an indexed document with default values"""
        doc_id = uuid4()
        
        indexed = IndexedDocument(
            documentId=doc_id,
            cleanedText="cleaned text",
            searchableContent="cleaned text"
        )
        
        assert indexed.keywords == []
        assert isinstance(indexed.indexTimestamp, datetime)
    
    def test_indexed_document_with_empty_keywords(self):
        """Test that keywords can be an empty list"""
        doc_id = uuid4()
        
        indexed = IndexedDocument(
            documentId=doc_id,
            cleanedText="text",
            keywords=[],
            searchableContent="text"
        )
        
        assert indexed.keywords == []
    
    def test_indexed_document_with_multiple_keywords(self):
        """Test indexed document with multiple keywords"""
        doc_id = uuid4()
        
        keywords = ["invoice", "payment", "date", "amount", "customer"]
        indexed = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment details",
            keywords=keywords,
            searchableContent="invoice payment details"
        )
        
        assert len(indexed.keywords) == 5
        assert indexed.keywords == keywords
    
    def test_indexed_document_missing_required_fields(self):
        """Test that creating an indexed document without required fields raises error"""
        with pytest.raises(ValidationError):
            IndexedDocument(cleanedText="text")
    
    def test_indexed_document_serialization(self):
        """Test that indexed document can be serialized to dict"""
        doc_id = uuid4()
        
        indexed = IndexedDocument(
            documentId=doc_id,
            cleanedText="cleaned text",
            keywords=["cleaned", "text"],
            searchableContent="cleaned text"
        )
        
        indexed_dict = indexed.model_dump()
        assert indexed_dict["cleanedText"] == "cleaned text"
        assert indexed_dict["keywords"] == ["cleaned", "text"]
        assert indexed_dict["searchableContent"] == "cleaned text"


class TestModelIntegration:
    """Integration tests for model interactions"""
    
    def test_document_to_ocr_result_flow(self):
        """Test the flow from Document to OCRResult"""
        # Create a document
        doc = Document(
            filename="test.pdf",
            storageUrl="s3://bucket/test.pdf",
            contentType="application/pdf"
        )
        
        # Simulate OCR processing
        doc.status = DocumentStatus.PROCESSING
        
        # Create OCR result
        ocr_result = OCRResult(
            documentId=doc.id,
            rawText="Extracted text from document",
            confidence=0.92,
            processingTime=3.2,
            metadata={"pages": 1}
        )
        
        assert ocr_result.documentId == doc.id
        assert doc.status == DocumentStatus.PROCESSING
    
    def test_ocr_result_to_indexed_document_flow(self):
        """Test the flow from OCRResult to IndexedDocument"""
        doc_id = uuid4()
        
        # Create OCR result
        ocr_result = OCRResult(
            documentId=doc_id,
            rawText="Raw Text With Capitals",
            confidence=0.88,
            processingTime=2.1
        )
        
        # Create indexed document from cleaned OCR text
        indexed = IndexedDocument(
            documentId=ocr_result.documentId,
            cleanedText="raw text with capitals",
            keywords=["raw", "text", "capitals"],
            searchableContent="raw text with capitals"
        )
        
        assert indexed.documentId == ocr_result.documentId
        assert indexed.cleanedText.islower()
    
    def test_full_document_processing_flow(self):
        """Test the complete flow: Document -> OCRResult -> IndexedDocument"""
        # Step 1: Upload document
        doc = Document(
            filename="invoice.pdf",
            storageUrl="s3://bucket/invoice.pdf",
            contentType="application/pdf"
        )
        assert doc.status == DocumentStatus.UPLOADED
        
        # Step 2: Process with OCR
        doc.status = DocumentStatus.PROCESSING
        ocr_result = OCRResult(
            documentId=doc.id,
            rawText="INVOICE\nAmount: $100",
            confidence=0.95,
            processingTime=1.8
        )
        
        # Step 3: Index document
        indexed = IndexedDocument(
            documentId=doc.id,
            cleanedText="invoice amount $100",
            keywords=["invoice", "amount"],
            searchableContent="invoice amount 100"
        )
        doc.status = DocumentStatus.INDEXED
        
        # Verify the complete flow
        assert doc.id == ocr_result.documentId == indexed.documentId
        assert doc.status == DocumentStatus.INDEXED
        assert ocr_result.confidence > 0.9
        assert len(indexed.keywords) > 0

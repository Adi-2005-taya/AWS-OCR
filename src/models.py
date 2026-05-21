"""Data models for OCR Document Extraction System

This module defines the core data models used throughout the system.
"""

from datetime import UTC, datetime
from typing import Any, Dict, List
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.constants import DocumentStatus


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime"""
    return datetime.now(UTC)


class Document(BaseModel):
    """Document model representing an uploaded document image.
    
    Attributes:
        id: Unique identifier for the document
        filename: Original filename of the uploaded document
        uploadTimestamp: Timestamp when the document was uploaded
        storageUrl: URL where the document is stored
        contentType: MIME type of the document
        status: Current processing status of the document
    """
    
    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "filename": "invoice.pdf",
                "uploadTimestamp": "2024-01-15T10:30:00Z",
                "storageUrl": "s3://bucket/documents/invoice.pdf",
                "contentType": "application/pdf",
                "status": "UPLOADED"
            }
        }
    )
    
    id: UUID = Field(default_factory=uuid4, description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    uploadTimestamp: datetime = Field(
        default_factory=utc_now,
        description="Upload timestamp"
    )
    storageUrl: str = Field(..., description="Storage location URL")
    contentType: str = Field(..., description="MIME type of the document")
    status: DocumentStatus = Field(
        default=DocumentStatus.UPLOADED,
        description="Current processing status"
    )
    ownerId: str | None = Field(
        default=None,
        description="User ID of the document owner"
    )
    sharedWith: List[str] = Field(
        default_factory=list,
        description="List of user IDs with access to this document"
    )


class OCRResult(BaseModel):
    """OCR result model containing extracted text and metadata.
    
    Attributes:
        documentId: Reference to the source document
        rawText: Raw text extracted by OCR service
        confidence: Confidence score of the OCR extraction (0.0 to 1.0)
        processingTime: Time taken to process the document in seconds
        metadata: Additional metadata from the OCR service
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "documentId": "123e4567-e89b-12d3-a456-426614174000",
                "rawText": "Invoice\nDate: 2024-01-15\nAmount: $100.00",
                "confidence": 0.95,
                "processingTime": 2.5,
                "metadata": {
                    "ocrEngine": "tesseract",
                    "language": "eng",
                    "pageCount": 1
                }
            }
        }
    )
    
    documentId: UUID = Field(..., description="Reference to source document")
    rawText: str = Field(..., description="Raw extracted text")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="OCR confidence score (0.0 to 1.0)"
    )
    processingTime: float = Field(
        ...,
        gt=0.0,
        description="Processing time in seconds"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional OCR metadata"
    )


class IndexedDocument(BaseModel):
    """Indexed document model for search functionality.
    
    Attributes:
        documentId: Reference to the source document
        cleanedText: Cleaned and normalized text
        keywords: Extracted keywords for search
        indexTimestamp: Timestamp when the document was indexed
        searchableContent: Processed content optimized for search
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "documentId": "123e4567-e89b-12d3-a456-426614174000",
                "cleanedText": "invoice date 2024-01-15 amount $100.00",
                "keywords": ["invoice", "date", "amount"],
                "indexTimestamp": "2024-01-15T10:35:00Z",
                "searchableContent": "invoice date 2024 01 15 amount 100 00"
            }
        }
    )
    
    documentId: UUID = Field(..., description="Reference to source document")
    cleanedText: str = Field(..., description="Cleaned and normalized text")
    keywords: List[str] = Field(
        default_factory=list,
        description="Extracted keywords"
    )
    indexTimestamp: datetime = Field(
        default_factory=utc_now,
        description="Index timestamp"
    )
    searchableContent: str = Field(..., description="Search-optimized content")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g. per-page text)"
    )

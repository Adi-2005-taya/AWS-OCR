"""Document processor for DocuSense System

This module orchestrates the document processing pipeline:
1. Validate document status
2. Update status to PROCESSING
3. Perform OCR
4. Clean extracted text
5. Index document
6. Update status to INDEXED or FAILED

Requirements: 2.3, 2.4, 2.6, 4.3, 6.2, 6.3
"""

import structlog
from typing import Optional
from uuid import UUID

from src.constants import DocumentStatus
from src.exceptions import (
    DocumentProcessingError,
    InvalidDocumentStatusError,
    OCRError,
    SearchIndexError
)
from src.models import Document, IndexedDocument, OCRResult
from src.ocr_service import OCRServiceFactory, OCRServiceInterface
from src.search_engine import SearchEngineFactory, SearchEngineInterface
from src.storage import StorageFactory, StorageInterface
from src.text_cleaner import TextCleaner, get_text_cleaner

logger = structlog.get_logger(__name__)


class DocumentProcessor:
    """Document processor that orchestrates the OCR workflow.
    
    This class coordinates the entire document processing pipeline from
    OCR extraction through text cleaning to search indexing.
    """
    
    def __init__(
        self,
        storage: Optional[StorageInterface] = None,
        ocr_service: Optional[OCRServiceInterface] = None,
        text_cleaner: Optional[TextCleaner] = None,
        search_engine: Optional[SearchEngineInterface] = None
    ):
        """Initialize document processor.
        
        Args:
            storage: Storage interface (creates default if not provided)
            ocr_service: OCR service (creates default if not provided)
            text_cleaner: Text cleaner (creates default if not provided)
            search_engine: Search engine (creates default if not provided)
        """
        self.storage = storage or StorageFactory.create_storage()
        self.ocr_service = ocr_service or OCRServiceFactory.create_service()
        self.text_cleaner = text_cleaner or get_text_cleaner()
        self.search_engine = search_engine or SearchEngineFactory.create_engine()
        self.logger = logger.bind(component="document_processor")
    
    def process_document(
        self,
        document: Document
    ) -> IndexedDocument:
        """Process a document through the full OCR pipeline.
        
        This method orchestrates:
        1. Status validation (must be UPLOADED)
        2. Status update to PROCESSING
        3. OCR extraction
        4. Text cleaning
        5. Document indexing
        6. Status update to INDEXED (or FAILED on error)
        
        Args:
            document: Document to process
            
        Returns:
            IndexedDocument with indexed content
            
        Raises:
            InvalidDocumentStatusError: If document status is not UPLOADED
            DocumentProcessingError: If processing fails
        """
        document_id = document.id
        
        self.logger.info(
            "Starting document processing",
            document_id=str(document_id),
            filename=document.filename
        )
        
        try:
            # Validate document status
            if document.status != DocumentStatus.UPLOADED:
                raise InvalidDocumentStatusError(
                    f"Document must be in UPLOADED status, got {document.status}",
                    error_code="INVALID_STATUS",
                    details={
                        "document_id": str(document_id),
                        "current_status": document.status,
                        "required_status": DocumentStatus.UPLOADED
                    }
                )
            
            # Update status to PROCESSING
            document.status = DocumentStatus.PROCESSING
            self.logger.info(
                "Document status updated to PROCESSING",
                document_id=str(document_id)
            )
            
            # Perform OCR
            try:
                self.logger.info(
                    "Starting OCR extraction",
                    document_id=str(document_id),
                    storage_url=document.storageUrl
                )
                
                # Download document from storage
                document_data = self.storage.download(document_id)
                
                # Extract text using OCR service
                ocr_result = self.ocr_service.extract_text(
                    document_data,
                    document.id
                )
                
                self.logger.info(
                    "OCR extraction completed",
                    document_id=str(document_id),
                    confidence=ocr_result.confidence,
                    processing_time=ocr_result.processingTime,
                    text_length=len(ocr_result.rawText)
                )
                
            except Exception as e:
                # Update status to FAILED
                document.status = DocumentStatus.FAILED
                
                self.logger.error(
                    "OCR extraction failed",
                    document_id=str(document_id),
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                raise DocumentProcessingError(
                    f"OCR extraction failed: {str(e)}",
                    error_code="OCR_FAILED",
                    details={
                        "document_id": str(document_id),
                        "filename": document.filename,
                        "error": str(e)
                    }
                ) from e
            
            # Clean extracted text
            try:
                self.logger.info(
                    "Starting text cleaning",
                    document_id=str(document_id)
                )
                
                cleaned_text = self.text_cleaner.clean(ocr_result.rawText)
                keywords = self.text_cleaner.extract_keywords(cleaned_text)
                
                self.logger.info(
                    "Text cleaning completed",
                    document_id=str(document_id),
                    cleaned_length=len(cleaned_text),
                    keyword_count=len(keywords)
                )
                
            except Exception as e:
                # Update status to FAILED
                document.status = DocumentStatus.FAILED
                
                self.logger.error(
                    "Text cleaning failed",
                    document_id=str(document_id),
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                raise DocumentProcessingError(
                    f"Text cleaning failed: {str(e)}",
                    error_code="CLEANING_FAILED",
                    details={
                        "document_id": str(document_id),
                        "error": str(e)
                    }
                ) from e
            
            # Index document
            try:
                self.logger.info(
                    "Starting document indexing",
                    document_id=str(document_id)
                )
                
                # Inject content type into metadata so web.py can serve it with the right mime type
                final_metadata = ocr_result.metadata.copy()
                if hasattr(document, 'contentType'):
                    final_metadata['contentType'] = document.contentType

                indexed_doc = IndexedDocument(
                    documentId=document_id,
                    cleanedText=cleaned_text,
                    keywords=keywords,
                    searchableContent=cleaned_text.lower(),
                    metadata=final_metadata,  # carries per-page text and content type
                    ownerId=getattr(document, "ownerId", None),
                )
                
                self.search_engine.index(indexed_doc)
                
                self.logger.info(
                    "Document indexing completed",
                    document_id=str(document_id)
                )
                
            except Exception as e:
                # Update status to FAILED
                document.status = DocumentStatus.FAILED
                
                self.logger.error(
                    "Document indexing failed",
                    document_id=str(document_id),
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                raise DocumentProcessingError(
                    f"Document indexing failed: {str(e)}",
                    error_code="INDEXING_FAILED",
                    details={
                        "document_id": str(document_id),
                        "error": str(e)
                    }
                ) from e
            
            # Update status to INDEXED
            document.status = DocumentStatus.INDEXED
            
            self.logger.info(
                "Document processing completed successfully",
                document_id=str(document_id),
                final_status=document.status
            )
            
            return indexed_doc
            
        except (InvalidDocumentStatusError, DocumentProcessingError):
            # Re-raise known errors
            raise
        except Exception as e:
            # Catch any unexpected errors
            document.status = DocumentStatus.FAILED
            
            self.logger.error(
                "Unexpected error during document processing",
                document_id=str(document_id),
                error=str(e),
                error_type=type(e).__name__
            )
            
            raise DocumentProcessingError(
                f"Unexpected error during processing: {str(e)}",
                error_code="PROCESSING_FAILED",
                details={
                    "document_id": str(document_id),
                    "error": str(e)
                }
            ) from e


def create_document_processor(
    storage: Optional[StorageInterface] = None,
    ocr_service: Optional[OCRServiceInterface] = None,
    text_cleaner: Optional[TextCleaner] = None,
    search_engine: Optional[SearchEngineInterface] = None
) -> DocumentProcessor:
    """Create a document processor instance.
    
    Args:
        storage: Optional storage interface
        ocr_service: Optional OCR service
        text_cleaner: Optional text cleaner
        search_engine: Optional search engine
        
    Returns:
        DocumentProcessor instance
    """
    return DocumentProcessor(
        storage=storage,
        ocr_service=ocr_service,
        text_cleaner=text_cleaner,
        search_engine=search_engine
    )

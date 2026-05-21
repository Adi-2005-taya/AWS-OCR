"""Base exception classes for OCR Document Extraction System

This module defines the exception hierarchy for the application,
providing structured error handling across all components.
"""

from typing import Any, Optional


class OCRSystemError(Exception):
    """Base exception for all OCR system errors.
    
    All custom exceptions in the system should inherit from this class.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initialize the exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error context
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
    
    def __str__(self) -> str:
        """String representation of the exception."""
        if self.details:
            return f"{self.message} (code: {self.error_code}, details: {self.details})"
        return f"{self.message} (code: {self.error_code})"


# Storage-related exceptions

class StorageError(OCRSystemError):
    """Base exception for storage-related errors."""
    pass


class DocumentNotFoundError(StorageError):
    """Raised when a document cannot be found in storage."""
    pass


class StorageUploadError(StorageError):
    """Raised when document upload fails."""
    pass


class StorageDownloadError(StorageError):
    """Raised when document download fails."""
    pass


class StorageDeleteError(StorageError):
    """Raised when document deletion fails."""
    pass


# Validation-related exceptions

class ValidationError(OCRSystemError):
    """Base exception for validation errors."""
    pass


class InvalidFileTypeError(ValidationError):
    """Raised when an uploaded file has an invalid type."""
    pass


class InvalidDocumentStatusError(ValidationError):
    """Raised when a document is in an invalid status for an operation."""
    pass


class MalwareDetectedError(ValidationError):
    """Raised when malware is detected in an uploaded file."""
    pass


# OCR-related exceptions

class OCRError(OCRSystemError):
    """Base exception for OCR processing errors."""
    pass


class OCRProcessingError(OCRError):
    """Raised when OCR processing fails."""
    pass


class OCRRateLimitError(OCRError):
    """Raised when OCR rate limit is exceeded."""
    pass


class OCRServiceUnavailableError(OCRError):
    """Raised when the OCR service is unavailable."""
    pass


# Text processing exceptions

class TextProcessingError(OCRSystemError):
    """Base exception for text processing errors."""
    pass


class TextCleaningError(TextProcessingError):
    """Raised when text cleaning fails."""
    pass


class EmptyTextError(TextProcessingError):
    """Raised when text cleaning produces empty output."""
    pass


# Search-related exceptions

class SearchError(OCRSystemError):
    """Base exception for search-related errors."""
    pass


class IndexingError(SearchError):
    """Raised when document indexing fails."""
    pass


class SearchIndexError(SearchError):
    """Raised when search index operations fail."""
    pass


class SearchQueryError(SearchError):
    """Raised when a search query is invalid or fails."""
    pass


class EmptyQueryError(SearchQueryError):
    """Raised when a search query is empty."""
    pass


class SearchServiceUnavailableError(SearchError):
    """Raised when the search service is unavailable."""
    pass


# Processing pipeline exceptions

class ProcessingError(OCRSystemError):
    """Base exception for document processing pipeline errors."""
    pass


class ProcessingPipelineError(ProcessingError):
    """Raised when the processing pipeline fails."""
    pass


class DocumentProcessingError(ProcessingError):
    """Raised when document processing fails at any stage."""
    pass


# Security exceptions

class SecurityError(OCRSystemError):
    """Base exception for security-related errors."""
    pass


class AccessDeniedError(SecurityError):
    """Raised when access to a resource is denied."""
    pass


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""
    pass


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""
    pass


# Configuration exceptions

class ConfigurationError(OCRSystemError):
    """Base exception for configuration errors."""
    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""
    pass


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""
    pass


# Retry and resilience exceptions

class RetryableError(OCRSystemError):
    """Base exception for errors that can be retried.
    
    This exception indicates that the operation failed but may succeed
    if retried with exponential backoff.
    """
    pass


class RetryExhaustedError(OCRSystemError):
    """Raised when all retry attempts have been exhausted."""
    pass

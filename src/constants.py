"""Constants for OCR Document Extraction System

This module defines system-wide constants used across components.
"""

from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status states"""
    
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class FileType(str, Enum):
    """Supported file types for document upload"""
    
    PNG = "image/png"
    JPEG = "image/jpeg"
    JPG = "image/jpg"
    TIFF = "image/tiff"
    PDF = "application/pdf"


# Default configuration values
DEFAULT_OCR_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_INITIAL_DELAY = 1.0
DEFAULT_RETRY_MAX_DELAY = 60.0
DEFAULT_RETRY_EXPONENTIAL_BASE = 2.0

# Validation limits
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_FILENAME_LENGTH = 255
MAX_QUERY_LENGTH = 1000

# Processing timeouts
OCR_PROCESSING_TIMEOUT_SECONDS = 300  # 5 minutes
INDEXING_TIMEOUT_SECONDS = 60  # 1 minute
SEARCH_TIMEOUT_SECONDS = 30  # 30 seconds

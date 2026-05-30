"""Validation utilities for DocuSense System

This module provides validation functions for file uploads and other inputs.
"""

from typing import List

from config.settings import get_settings
from src.constants import FileType
from src.exceptions import InvalidFileTypeError


class FileTypeValidator:
    """Validator for file types based on allowlist.
    
    This validator checks uploaded files against a configured allowlist
    of supported file types to ensure only valid formats are processed.
    """
    
    def __init__(self, allowed_types: List[str] | None = None) -> None:
        """Initialize the file type validator.
        
        Args:
            allowed_types: List of allowed MIME types. If None, uses settings.
        """
        if allowed_types is None:
            settings = get_settings()
            allowed_types = settings.security.allowed_file_types
        
        self.allowed_types = set(allowed_types)
    
    def validate(self, content_type: str) -> None:
        """Validate that a file type is allowed.
        
        Args:
            content_type: MIME type of the file to validate
            
        Raises:
            InvalidFileTypeError: If the file type is not in the allowlist
        """
        if content_type not in self.allowed_types:
            raise InvalidFileTypeError(
                f"File type '{content_type}' is not allowed",
                error_code="INVALID_FILE_TYPE",
                details={
                    "content_type": content_type,
                    "allowed_types": sorted(self.allowed_types)
                }
            )
    
    def is_valid(self, content_type: str) -> bool:
        """Check if a file type is valid without raising an exception.
        
        Args:
            content_type: MIME type of the file to check
            
        Returns:
            True if the file type is allowed, False otherwise
        """
        return content_type in self.allowed_types
    
    def get_allowed_types(self) -> List[str]:
        """Get the list of allowed file types.
        
        Returns:
            Sorted list of allowed MIME types
        """
        return sorted(self.allowed_types)


def validate_file_type(content_type: str, allowed_types: List[str] | None = None) -> None:
    """Convenience function to validate a file type.
    
    Args:
        content_type: MIME type of the file to validate
        allowed_types: Optional list of allowed types. If None, uses settings.
        
    Raises:
        InvalidFileTypeError: If the file type is not allowed
    """
    validator = FileTypeValidator(allowed_types)
    validator.validate(content_type)


def is_valid_file_type(content_type: str, allowed_types: List[str] | None = None) -> bool:
    """Convenience function to check if a file type is valid.
    
    Args:
        content_type: MIME type of the file to check
        allowed_types: Optional list of allowed types. If None, uses settings.
        
    Returns:
        True if the file type is allowed, False otherwise
    """
    validator = FileTypeValidator(allowed_types)
    return validator.is_valid(content_type)

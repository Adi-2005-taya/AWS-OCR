"""Text cleaning and normalization for DocuSense System

This module provides text cleaning functions to normalize and structure
OCR-extracted text for indexing and search.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import re
import unicodedata
from typing import Dict, List

from src.exceptions import TextCleaningError, EmptyTextError


class TextCleaner:
    """Text cleaning and normalization service.
    
    This class provides methods to clean and normalize OCR-extracted text
    by removing irregular whitespace, correcting common OCR errors, removing
    non-printable characters, and normalizing case.
    """
    
    # Common OCR error patterns and their corrections
    OCR_ERROR_PATTERNS = {
        r'\brn\b': 'm',  # "rn" often misread as "m" (word boundary)
        r'(?<!\w)l(?!\w)': 'I',   # standalone lowercase "l" → uppercase "I"
        r'(?<!\w)O(?!\w)': '0',   # standalone uppercase "O" → zero
    }
    
    def __init__(self):
        """Initialize text cleaner."""
        pass
    
    def clean(self, text: str) -> str:
        """Clean and normalize text through all cleaning steps.
        
        This is the main entry point that applies all cleaning operations
        in the correct order.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned and normalized text
            
        Raises:
            EmptyTextError: If cleaning produces empty output from valid input
            TextCleaningError: If cleaning fails
        """
        if not text:
            raise EmptyTextError(
                "Cannot clean empty text",
                error_code="EMPTY_INPUT",
                details={"input_length": 0}
            )
        
        try:
            # Apply cleaning steps in order
            cleaned = text
            cleaned = self.normalize_whitespace(cleaned)
            cleaned = self.correct_ocr_errors(cleaned)
            cleaned = self.remove_non_printable(cleaned)
            cleaned = self.normalize_case(cleaned)
            
            # Ensure result is not empty
            if not cleaned or cleaned.isspace():
                raise EmptyTextError(
                    "Text cleaning produced empty output",
                    error_code="EMPTY_OUTPUT",
                    details={
                        "input_length": len(text),
                        "input_preview": text[:100]
                    }
                )
            
            return cleaned
            
        except EmptyTextError:
            raise
        except Exception as e:
            raise TextCleaningError(
                f"Failed to clean text: {str(e)}",
                error_code="CLEANING_FAILED",
                details={"error": str(e)}
            ) from e
    
    def normalize_whitespace(self, text: str) -> str:
        """Normalize irregular whitespace.
        
        Removes multiple spaces, tabs, and irregular newlines, replacing
        them with consistent single spaces and standard line breaks.
        
        Args:
            text: Text with irregular whitespace
            
        Returns:
            Text with normalized whitespace
        """
        # Replace tabs with spaces
        text = text.replace('\t', ' ')
        
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Normalize line breaks (handle \r\n, \r, \n)
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        # Remove multiple consecutive newlines (keep max 2 for paragraph breaks)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove spaces at start/end of lines
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def correct_ocr_errors(self, text: str) -> str:
        """Correct common OCR errors.
        
        Applies pattern-based corrections for common OCR misreadings
        such as "rn" → "m", "l" → "I", etc.
        
        Args:
            text: Text with potential OCR errors
            
        Returns:
            Text with corrected OCR errors
        """
        corrected = text
        
        # Apply each error pattern correction
        for pattern, replacement in self.OCR_ERROR_PATTERNS.items():
            corrected = re.sub(pattern, replacement, corrected)
        
        return corrected
    
    def remove_non_printable(self, text: str) -> str:
        """Remove non-printable characters.
        
        Removes control characters and other non-printable characters
        while preserving standard whitespace (spaces, tabs, newlines).
        
        Args:
            text: Text with potential non-printable characters
            
        Returns:
            Text with non-printable characters removed
        """
        # Keep only printable characters and standard whitespace
        cleaned = []
        for char in text:
            # Keep if printable or standard whitespace
            if char.isprintable() or char in (' ', '\t', '\n', '\r'):
                cleaned.append(char)
            # Also keep if it's a normal space category
            elif unicodedata.category(char).startswith('Z'):
                cleaned.append(' ')
        
        return ''.join(cleaned)
    
    def normalize_case(self, text: str) -> str:
        """Normalize case for indexing.
        
        Converts text to lowercase for consistent indexing and search.
        
        Args:
            text: Text with mixed case
            
        Returns:
            Lowercase text
        """
        return text.lower()
    
    def extract_keywords(self, text: str, min_length: int = 3, max_keywords: int = 50) -> List[str]:
        """Extract keywords from cleaned text.
        
        Extracts significant words from text for indexing, filtering out
        common stop words and very short words.
        
        Args:
            text: Cleaned text
            min_length: Minimum word length to include
            max_keywords: Maximum number of keywords to return
            
        Returns:
            List of keywords
        """
        # Common stop words to exclude
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were',
            'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'should', 'could', 'may', 'might', 'must',
            'can', 'this', 'that', 'these', 'those', 'a', 'an'
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter and deduplicate
        keywords = []
        seen = set()
        
        for word in words:
            if (len(word) >= min_length and 
                word not in stop_words and 
                word not in seen):
                keywords.append(word)
                seen.add(word)
                
                if len(keywords) >= max_keywords:
                    break
        
        return keywords


# Global text cleaner instance
_text_cleaner: TextCleaner = None


def get_text_cleaner() -> TextCleaner:
    """Get the global text cleaner instance.
    
    Returns:
        TextCleaner instance
    """
    global _text_cleaner
    if _text_cleaner is None:
        _text_cleaner = TextCleaner()
    return _text_cleaner


def clean_text(text: str) -> str:
    """Convenience function to clean text.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text
        
    Raises:
        EmptyTextError: If cleaning produces empty output
        TextCleaningError: If cleaning fails
    """
    cleaner = get_text_cleaner()
    return cleaner.clean(text)

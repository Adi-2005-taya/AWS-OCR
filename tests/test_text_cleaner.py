"""Unit tests for text cleaning

Tests cover:
- Whitespace normalization
- OCR error correction
- Non-printable character removal
- Case normalization
- Text cleaning invariant
- Keyword extraction
"""

import pytest

from src.exceptions import EmptyTextError, TextCleaningError
from src.text_cleaner import TextCleaner, clean_text, get_text_cleaner


class TestTextCleaner:
    """Tests for TextCleaner class."""
    
    def test_text_cleaner_initialization(self):
        """Test text cleaner can be initialized."""
        cleaner = TextCleaner()
        assert cleaner is not None
    
    def test_normalize_whitespace_multiple_spaces(self):
        """Test normalizing multiple spaces to single space."""
        cleaner = TextCleaner()
        text = "Hello    world   test"
        
        result = cleaner.normalize_whitespace(text)
        
        assert result == "Hello world test"
    
    def test_normalize_whitespace_tabs(self):
        """Test replacing tabs with spaces."""
        cleaner = TextCleaner()
        text = "Hello\tworld\ttest"
        
        result = cleaner.normalize_whitespace(text)
        
        assert result == "Hello world test"
    
    def test_normalize_whitespace_newlines(self):
        """Test normalizing different newline types."""
        cleaner = TextCleaner()
        
        # Test \r\n
        assert cleaner.normalize_whitespace("Hello\r\nworld") == "Hello\nworld"
        
        # Test \r
        assert cleaner.normalize_whitespace("Hello\rworld") == "Hello\nworld"
        
        # Test multiple \n
        assert cleaner.normalize_whitespace("Hello\n\n\n\nworld") == "Hello\n\nworld"
    
    def test_normalize_whitespace_line_trimming(self):
        """Test trimming spaces at start/end of lines."""
        cleaner = TextCleaner()
        text = "  Hello  \n  world  \n  test  "
        
        result = cleaner.normalize_whitespace(text)
        
        assert result == "Hello\nworld\ntest"
    
    def test_correct_ocr_errors_rn_to_m(self):
        """Test correcting 'rn' to 'm'."""
        cleaner = TextCleaner()
        text = "The rn is correct"
        
        result = cleaner.correct_ocr_errors(text)
        
        assert result == "The m is correct"
    
    def test_correct_ocr_errors_l_to_I(self):
        """Test correcting standalone 'l' to 'I'."""
        cleaner = TextCleaner()
        text = "l think this is correct"
        
        result = cleaner.correct_ocr_errors(text)
        
        assert result == "I think this is correct"
    
    def test_correct_ocr_errors_O_to_0(self):
        """Test correcting standalone 'O' to '0'."""
        cleaner = TextCleaner()
        text = "The number is O"
        
        result = cleaner.correct_ocr_errors(text)
        
        assert result == "The number is 0"
    
    def test_remove_non_printable_control_chars(self):
        """Test removing control characters."""
        cleaner = TextCleaner()
        text = "Hello\x00\x01\x02world"
        
        result = cleaner.remove_non_printable(text)
        
        assert result == "Helloworld"
    
    def test_remove_non_printable_preserves_whitespace(self):
        """Test that standard whitespace is preserved."""
        cleaner = TextCleaner()
        text = "Hello world\ntest\ttab"
        
        result = cleaner.remove_non_printable(text)
        
        assert result == "Hello world\ntest\ttab"
    
    def test_normalize_case(self):
        """Test case normalization to lowercase."""
        cleaner = TextCleaner()
        text = "Hello WORLD Test"
        
        result = cleaner.normalize_case(text)
        
        assert result == "hello world test"
    
    def test_clean_full_pipeline(self):
        """Test complete cleaning pipeline."""
        cleaner = TextCleaner()
        text = "  Hello    WORLD  \n\n\n  Test  \t  rn  "
        
        result = cleaner.clean(text)
        
        # Should be normalized, lowercase, with corrected OCR errors
        assert "hello" in result
        assert "world" in result
        assert "test" in result
        assert "  " not in result  # No multiple spaces
        assert result == result.lower()  # All lowercase
    
    def test_clean_empty_input_raises_error(self):
        """Test that cleaning empty input raises EmptyTextError."""
        cleaner = TextCleaner()
        
        with pytest.raises(EmptyTextError) as exc_info:
            cleaner.clean("")
        
        assert exc_info.value.error_code == "EMPTY_INPUT"
    
    def test_clean_whitespace_only_raises_error(self):
        """Test that cleaning whitespace-only input raises EmptyTextError."""
        cleaner = TextCleaner()
        
        with pytest.raises(EmptyTextError) as exc_info:
            cleaner.clean("   \n\n\t\t   ")
        
        assert exc_info.value.error_code == "EMPTY_OUTPUT"
    
    def test_clean_preserves_meaningful_content(self):
        """Test that cleaning preserves meaningful content."""
        cleaner = TextCleaner()
        text = "Invoice #12345\nDate: 2024-01-15\nAmount: $100.00"
        
        result = cleaner.clean(text)
        
        assert "invoice" in result
        assert "12345" in result
        assert "2024" in result
        assert "100" in result
    
    def test_extract_keywords_basic(self):
        """Test extracting keywords from text."""
        cleaner = TextCleaner()
        text = "invoice payment customer order total"
        
        keywords = cleaner.extract_keywords(text)
        
        assert "invoice" in keywords
        assert "payment" in keywords
        assert "customer" in keywords
        assert "order" in keywords
        assert "total" in keywords
    
    def test_extract_keywords_filters_stop_words(self):
        """Test that stop words are filtered out."""
        cleaner = TextCleaner()
        text = "the invoice and the payment for the customer"
        
        keywords = cleaner.extract_keywords(text)
        
        assert "invoice" in keywords
        assert "payment" in keywords
        assert "customer" in keywords
        assert "the" not in keywords
        assert "and" not in keywords
        assert "for" not in keywords
    
    def test_extract_keywords_filters_short_words(self):
        """Test that short words are filtered out."""
        cleaner = TextCleaner()
        text = "invoice is a document"
        
        keywords = cleaner.extract_keywords(text, min_length=3)
        
        assert "invoice" in keywords
        assert "document" in keywords
        assert "is" not in keywords  # Too short
    
    def test_extract_keywords_deduplicates(self):
        """Test that duplicate keywords are removed."""
        cleaner = TextCleaner()
        text = "invoice invoice payment payment customer"
        
        keywords = cleaner.extract_keywords(text)
        
        assert keywords.count("invoice") == 1
        assert keywords.count("payment") == 1
        assert keywords.count("customer") == 1
    
    def test_extract_keywords_respects_max_limit(self):
        """Test that max_keywords limit is respected."""
        cleaner = TextCleaner()
        text = " ".join([f"word{i}" for i in range(100)])
        
        keywords = cleaner.extract_keywords(text, max_keywords=10)
        
        assert len(keywords) == 10
    
    def test_extract_keywords_case_insensitive(self):
        """Test that keyword extraction is case-insensitive."""
        cleaner = TextCleaner()
        text = "Invoice INVOICE invoice"
        
        keywords = cleaner.extract_keywords(text)
        
        assert len(keywords) == 1
        assert keywords[0] == "invoice"


class TestCleanTextFunction:
    """Tests for clean_text convenience function."""
    
    def test_clean_text_function(self):
        """Test clean_text convenience function."""
        text = "  Hello    WORLD  "
        
        result = clean_text(text)
        
        assert result == "hello world"
    
    def test_clean_text_raises_on_empty(self):
        """Test clean_text raises EmptyTextError on empty input."""
        with pytest.raises(EmptyTextError):
            clean_text("")


class TestGetTextCleaner:
    """Tests for get_text_cleaner singleton."""
    
    def test_get_text_cleaner_returns_instance(self):
        """Test get_text_cleaner returns TextCleaner instance."""
        cleaner = get_text_cleaner()
        
        assert isinstance(cleaner, TextCleaner)
    
    def test_get_text_cleaner_singleton(self):
        """Test get_text_cleaner returns same instance."""
        cleaner1 = get_text_cleaner()
        cleaner2 = get_text_cleaner()
        
        assert cleaner1 is cleaner2


class TestTextCleaningEdgeCases:
    """Tests for edge cases in text cleaning."""
    
    def test_clean_unicode_text(self):
        """Test cleaning text with Unicode characters."""
        cleaner = TextCleaner()
        text = "Café résumé naïve"
        
        result = cleaner.clean(text)
        
        assert "café" in result
        assert "résumé" in result
        assert "naïve" in result
    
    def test_clean_numbers_and_symbols(self):
        """Test cleaning text with numbers and symbols."""
        cleaner = TextCleaner()
        text = "Invoice #12345 - $100.00 (paid)"
        
        result = cleaner.clean(text)
        
        assert "12345" in result
        assert "100" in result
    
    def test_clean_very_long_text(self):
        """Test cleaning very long text."""
        cleaner = TextCleaner()
        text = "word " * 10000
        
        result = cleaner.clean(text)
        
        assert len(result) > 0
        assert "word" in result
    
    def test_clean_mixed_content(self):
        """Test cleaning text with mixed content types."""
        cleaner = TextCleaner()
        text = """
        INVOICE #12345
        Date: 2024-01-15
        Customer: John Doe
        
        Items:
        - Product A: $50.00
        - Product B: $50.00
        
        Total: $100.00
        """
        
        result = cleaner.clean(text)
        
        assert "invoice" in result
        assert "12345" in result
        assert "john" in result
        assert "doe" in result
        assert "product" in result
        assert "total" in result
    
    def test_normalize_whitespace_empty_lines(self):
        """Test handling of empty lines."""
        cleaner = TextCleaner()
        text = "Line 1\n\nLine 2\n\n\nLine 3"
        
        result = cleaner.normalize_whitespace(text)
        
        # Should preserve paragraph breaks (double newline)
        assert "Line 1\n\nLine 2\n\nLine 3" == result
    
    def test_clean_preserves_line_structure(self):
        """Test that cleaning preserves basic line structure."""
        cleaner = TextCleaner()
        text = "Line 1\nLine 2\nLine 3"
        
        result = cleaner.clean(text)
        
        lines = result.split('\n')
        assert len(lines) == 3


class TestTextCleaningInvariant:
    """Tests for text cleaning invariant (Requirement 3.5)."""
    
    def test_valid_input_produces_non_empty_output(self):
        """Test that valid input always produces non-empty output."""
        cleaner = TextCleaner()
        
        valid_inputs = [
            "Hello world",
            "Test",
            "123",
            "A",
            "!@#$%",
            "Mixed 123 content!",
        ]
        
        for text in valid_inputs:
            result = cleaner.clean(text)
            assert len(result) > 0, f"Failed for input: {text}"
            assert not result.isspace(), f"Output is only whitespace for: {text}"

"""Unit tests for validation utilities

Tests the file type validation functionality.
"""

import pytest

from config.settings import get_settings
from src.constants import FileType
from src.exceptions import InvalidFileTypeError
from src.validation import (
    FileTypeValidator,
    is_valid_file_type,
    validate_file_type,
)


class TestFileTypeValidator:
    """Tests for the FileTypeValidator class"""
    
    def test_validator_creation_with_default_settings(self):
        """Test creating validator with default settings from config"""
        validator = FileTypeValidator()
        
        allowed = validator.get_allowed_types()
        assert len(allowed) > 0
        assert "image/png" in allowed
        assert "image/jpeg" in allowed
        assert "application/pdf" in allowed
    
    def test_validator_creation_with_custom_types(self):
        """Test creating validator with custom allowed types"""
        custom_types = ["image/png", "image/jpeg"]
        validator = FileTypeValidator(allowed_types=custom_types)
        
        allowed = validator.get_allowed_types()
        assert len(allowed) == 2
        assert "image/png" in allowed
        assert "image/jpeg" in allowed
        assert "application/pdf" not in allowed
    
    def test_validate_allowed_type(self):
        """Test validating an allowed file type"""
        validator = FileTypeValidator(allowed_types=["image/png", "image/jpeg"])
        
        # Should not raise exception
        validator.validate("image/png")
        validator.validate("image/jpeg")
    
    def test_validate_disallowed_type(self):
        """Test validating a disallowed file type raises exception"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        with pytest.raises(InvalidFileTypeError) as exc_info:
            validator.validate("image/gif")
        
        error = exc_info.value
        assert "image/gif" in error.message
        assert error.error_code == "INVALID_FILE_TYPE"
        assert "content_type" in error.details
        assert error.details["content_type"] == "image/gif"
        assert "allowed_types" in error.details
    
    def test_is_valid_returns_true_for_allowed_type(self):
        """Test is_valid returns True for allowed types"""
        validator = FileTypeValidator(allowed_types=["image/png", "image/jpeg"])
        
        assert validator.is_valid("image/png") is True
        assert validator.is_valid("image/jpeg") is True
    
    def test_is_valid_returns_false_for_disallowed_type(self):
        """Test is_valid returns False for disallowed types"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        assert validator.is_valid("image/gif") is False
        assert validator.is_valid("application/pdf") is False
        assert validator.is_valid("text/plain") is False
    
    def test_get_allowed_types_returns_sorted_list(self):
        """Test get_allowed_types returns sorted list"""
        validator = FileTypeValidator(
            allowed_types=["image/tiff", "image/png", "application/pdf"]
        )
        
        allowed = validator.get_allowed_types()
        assert allowed == ["application/pdf", "image/png", "image/tiff"]
    
    def test_validate_all_file_type_enum_values(self):
        """Test validating all FileType enum values"""
        # Get all FileType enum values
        file_types = [ft.value for ft in FileType]
        validator = FileTypeValidator(allowed_types=file_types)
        
        # All should be valid
        for file_type in file_types:
            validator.validate(file_type)
            assert validator.is_valid(file_type) is True
    
    def test_validate_empty_string(self):
        """Test validating empty string raises exception"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        with pytest.raises(InvalidFileTypeError):
            validator.validate("")
    
    def test_validate_case_sensitive(self):
        """Test that validation is case-sensitive"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        # Exact match should work
        validator.validate("image/png")
        
        # Different case should fail
        with pytest.raises(InvalidFileTypeError):
            validator.validate("IMAGE/PNG")
        
        with pytest.raises(InvalidFileTypeError):
            validator.validate("Image/Png")


class TestValidateFileTypeFunction:
    """Tests for the validate_file_type convenience function"""
    
    def test_validate_with_default_settings(self):
        """Test validate_file_type with default settings"""
        # Should not raise for allowed types
        validate_file_type("image/png")
        validate_file_type("image/jpeg")
        validate_file_type("application/pdf")
    
    def test_validate_with_custom_types(self):
        """Test validate_file_type with custom allowed types"""
        custom_types = ["image/png"]
        
        # Should work for allowed type
        validate_file_type("image/png", allowed_types=custom_types)
        
        # Should fail for disallowed type
        with pytest.raises(InvalidFileTypeError):
            validate_file_type("image/jpeg", allowed_types=custom_types)
    
    def test_validate_invalid_type_raises_exception(self):
        """Test that invalid type raises InvalidFileTypeError"""
        with pytest.raises(InvalidFileTypeError) as exc_info:
            validate_file_type("application/x-executable", allowed_types=["image/png"])
        
        error = exc_info.value
        assert "application/x-executable" in error.message
        assert error.error_code == "INVALID_FILE_TYPE"


class TestIsValidFileTypeFunction:
    """Tests for the is_valid_file_type convenience function"""
    
    def test_is_valid_with_default_settings(self):
        """Test is_valid_file_type with default settings"""
        assert is_valid_file_type("image/png") is True
        assert is_valid_file_type("image/jpeg") is True
        assert is_valid_file_type("application/pdf") is True
        assert is_valid_file_type("text/plain") is False
    
    def test_is_valid_with_custom_types(self):
        """Test is_valid_file_type with custom allowed types"""
        custom_types = ["image/png", "image/jpeg"]
        
        assert is_valid_file_type("image/png", allowed_types=custom_types) is True
        assert is_valid_file_type("image/jpeg", allowed_types=custom_types) is True
        assert is_valid_file_type("application/pdf", allowed_types=custom_types) is False
    
    def test_is_valid_does_not_raise_exception(self):
        """Test that is_valid_file_type never raises exception"""
        # Should return False, not raise exception
        assert is_valid_file_type("invalid/type") is False
        assert is_valid_file_type("") is False
        assert is_valid_file_type("text/html") is False


class TestFileTypeValidationEdgeCases:
    """Tests for edge cases in file type validation"""
    
    def test_validator_with_empty_allowlist(self):
        """Test validator with empty allowlist rejects all types"""
        validator = FileTypeValidator(allowed_types=[])
        
        assert validator.is_valid("image/png") is False
        assert validator.is_valid("application/pdf") is False
        
        with pytest.raises(InvalidFileTypeError):
            validator.validate("image/png")
    
    def test_validator_with_duplicate_types(self):
        """Test validator handles duplicate types in allowlist"""
        validator = FileTypeValidator(
            allowed_types=["image/png", "image/png", "image/jpeg"]
        )
        
        allowed = validator.get_allowed_types()
        # Should deduplicate
        assert allowed.count("image/png") == 1
        assert len(allowed) == 2
    
    def test_validate_with_whitespace(self):
        """Test validation with whitespace in content type"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        # Whitespace should cause validation to fail
        with pytest.raises(InvalidFileTypeError):
            validator.validate(" image/png")
        
        with pytest.raises(InvalidFileTypeError):
            validator.validate("image/png ")
        
        with pytest.raises(InvalidFileTypeError):
            validator.validate("image/ png")
    
    def test_validate_with_parameters(self):
        """Test validation with MIME type parameters"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        # MIME type with parameters should fail if not in allowlist
        with pytest.raises(InvalidFileTypeError):
            validator.validate("image/png; charset=utf-8")
    
    def test_validate_all_standard_image_types(self):
        """Test validation of all standard image types"""
        image_types = [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/tiff",
            "image/gif",
            "image/bmp",
            "image/webp"
        ]
        
        validator = FileTypeValidator(allowed_types=image_types)
        
        for image_type in image_types:
            assert validator.is_valid(image_type) is True
            validator.validate(image_type)
    
    def test_validate_common_document_types(self):
        """Test validation of common document types"""
        doc_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        
        validator = FileTypeValidator(allowed_types=doc_types)
        
        for doc_type in doc_types:
            assert validator.is_valid(doc_type) is True
            validator.validate(doc_type)
    
    def test_reject_dangerous_file_types(self):
        """Test that dangerous file types are rejected"""
        validator = FileTypeValidator(allowed_types=["image/png"])
        
        dangerous_types = [
            "application/x-executable",
            "application/x-msdownload",
            "application/x-sh",
            "text/javascript",
            "application/javascript"
        ]
        
        for dangerous_type in dangerous_types:
            assert validator.is_valid(dangerous_type) is False
            with pytest.raises(InvalidFileTypeError):
                validator.validate(dangerous_type)


class TestFileTypeValidatorIntegration:
    """Integration tests for file type validation with settings"""
    
    def test_validator_uses_security_settings(self):
        """Test that validator correctly uses security settings"""
        settings = get_settings()
        validator = FileTypeValidator()
        
        # Should match settings
        allowed = validator.get_allowed_types()
        expected = sorted(settings.security.allowed_file_types)
        assert allowed == expected
    
    def test_validate_against_configured_types(self):
        """Test validation against configured allowed types"""
        settings = get_settings()
        validator = FileTypeValidator()
        
        # All configured types should be valid
        for file_type in settings.security.allowed_file_types:
            assert validator.is_valid(file_type) is True
            validator.validate(file_type)
    
    def test_file_type_enum_matches_settings(self):
        """Test that FileType enum values are in default settings"""
        settings = get_settings()
        allowed_types = set(settings.security.allowed_file_types)
        
        # All FileType enum values should be in allowed types
        for file_type in FileType:
            assert file_type.value in allowed_types

"""Tests for project infrastructure setup

This module tests that the core infrastructure components are properly configured.
"""

import pytest

from config.settings import Settings, get_settings, reload_settings
from src.exceptions import (
    OCRSystemError,
    StorageError,
    ValidationError,
    OCRError,
    SearchError,
)
from src.logging_config import configure_logging, get_logger


class TestExceptions:
    """Test base exception classes"""
    
    def test_base_exception_creation(self) -> None:
        """Test creating base OCRSystemError"""
        error = OCRSystemError("Test error", error_code="TEST_001", details={"key": "value"})
        
        assert error.message == "Test error"
        assert error.error_code == "TEST_001"
        assert error.details == {"key": "value"}
        assert "TEST_001" in str(error)
    
    def test_exception_hierarchy(self) -> None:
        """Test exception inheritance hierarchy"""
        storage_error = StorageError("Storage failed")
        validation_error = ValidationError("Validation failed")
        ocr_error = OCRError("OCR failed")
        search_error = SearchError("Search failed")
        
        # All should inherit from OCRSystemError
        assert isinstance(storage_error, OCRSystemError)
        assert isinstance(validation_error, OCRSystemError)
        assert isinstance(ocr_error, OCRSystemError)
        assert isinstance(search_error, OCRSystemError)
    
    def test_exception_default_error_code(self) -> None:
        """Test that error code defaults to class name"""
        error = StorageError("Test error")
        assert error.error_code == "StorageError"


class TestSettings:
    """Test configuration management"""
    
    def test_settings_creation(self) -> None:
        """Test creating settings instance"""
        settings = Settings()
        
        assert settings.app_name == "OCR Document Extraction"
        assert settings.app_version == "0.1.0"
        assert settings.environment in ["development", "staging", "production"]
    
    def test_storage_settings(self) -> None:
        """Test storage configuration"""
        settings = Settings()
        
        assert settings.storage.storage_type in ["local", "s3", "azure"]
        assert settings.storage.encryption_enabled is True
    
    def test_ocr_settings(self) -> None:
        """Test OCR configuration"""
        settings = Settings()
        
        assert settings.ocr.ocr_provider in ["tesseract", "aws", "google"]
        assert 0.0 <= settings.ocr.ocr_confidence_threshold <= 1.0
        assert settings.ocr.ocr_rate_limit > 0
    
    def test_search_settings(self) -> None:
        """Test search configuration"""
        settings = Settings()
        
        assert settings.search.search_backend in ["memory", "elasticsearch"]
        assert settings.search.search_index_name != ""
    
    def test_security_settings(self) -> None:
        """Test security configuration"""
        settings = Settings()
        
        assert isinstance(settings.security.allowed_file_types, list)
        assert len(settings.security.allowed_file_types) > 0
    
    def test_retry_settings(self) -> None:
        """Test retry configuration"""
        settings = Settings()
        
        assert settings.retry.retry_max_attempts > 0
        assert settings.retry.retry_initial_delay > 0
        assert settings.retry.retry_max_delay >= settings.retry.retry_initial_delay
        assert settings.retry.retry_exponential_base > 1.0
    
    def test_get_settings_singleton(self) -> None:
        """Test that get_settings returns the same instance"""
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
    
    def test_reload_settings(self) -> None:
        """Test reloading settings"""
        settings1 = get_settings()
        settings2 = reload_settings()
        
        # Should be different instances
        assert settings1 is not settings2
        # But should have same values
        assert settings1.app_name == settings2.app_name


class TestLogging:
    """Test logging configuration"""
    
    def test_configure_logging(self) -> None:
        """Test logging configuration"""
        # Should not raise any exceptions
        configure_logging(log_level="INFO", json_logs=False)
        configure_logging(log_level="DEBUG", json_logs=True)
    
    def test_get_logger(self) -> None:
        """Test getting logger instance"""
        configure_logging()
        logger = get_logger(__name__)
        
        assert logger is not None
        # Logger should have standard methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "debug")
    
    def test_logger_output(self) -> None:
        """Test that logger can output messages"""
        configure_logging(log_level="INFO")
        logger = get_logger(__name__)
        
        # Should not raise exceptions
        logger.info("test_message", key="value")
        logger.error("test_error", error="details")


class TestProjectStructure:
    """Test project structure and imports"""
    
    def test_src_package_import(self) -> None:
        """Test that src package can be imported"""
        import src
        assert hasattr(src, "__version__")
    
    def test_config_package_import(self) -> None:
        """Test that config package can be imported"""
        import config
        assert config is not None
    
    def test_tests_package_import(self) -> None:
        """Test that tests package can be imported"""
        import tests
        assert tests is not None

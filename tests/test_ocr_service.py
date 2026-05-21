"""Unit tests for OCR service abstraction

This module tests the OCR service interface and implementations.
"""

import time
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from src.exceptions import OCRError, OCRRateLimitError
from src.models import OCRResult
from src.ocr_service import (
    MockOCRService,
    OCRServiceFactory,
    OCRServiceInterface,
    RateLimitedOCRService,
    TesseractOCRService,
)


class TestOCRServiceInterface:
    """Test OCR service interface contract."""
    
    def test_interface_methods_exist(self):
        """Test that OCRServiceInterface defines required methods."""
        assert hasattr(OCRServiceInterface, 'extract_text')
        assert hasattr(OCRServiceInterface, 'get_supported_formats')


class TestMockOCRService:
    """Test mock OCR service implementation."""
    
    def test_mock_service_initialization(self):
        """Test mock service can be initialized with custom values."""
        service = MockOCRService(
            mock_text="Custom text",
            mock_confidence=0.85
        )
        assert service.mock_text == "Custom text"
        assert service.mock_confidence == 0.85
    
    def test_mock_service_default_initialization(self):
        """Test mock service uses default values."""
        service = MockOCRService()
        assert service.mock_text == "Mock OCR extracted text"
        assert service.mock_confidence == 0.95
    
    def test_mock_service_confidence_clamping(self):
        """Test mock service clamps confidence to valid range."""
        service_high = MockOCRService(mock_confidence=1.5)
        assert service_high.mock_confidence == 1.0
        
        service_low = MockOCRService(mock_confidence=-0.5)
        assert service_low.mock_confidence == 0.0
    
    def test_mock_extract_text(self):
        """Test mock service extracts text."""
        service = MockOCRService(
            mock_text="Test document text",
            mock_confidence=0.9
        )
        
        document_id = uuid4()
        image_data = b"fake image data"
        
        result = service.extract_text(image_data, document_id)
        
        assert isinstance(result, OCRResult)
        assert result.documentId == document_id
        assert result.rawText == "Test document text"
        assert result.confidence == 0.9
        assert result.processingTime > 0
        assert result.metadata["ocrEngine"] == "mock"
        assert result.metadata["language"] == "eng"
        assert result.metadata["imageSize"] == len(image_data)
    
    def test_mock_get_supported_formats(self):
        """Test mock service returns supported formats."""
        service = MockOCRService()
        formats = service.get_supported_formats()
        
        assert isinstance(formats, list)
        assert len(formats) > 0
        assert "image/png" in formats
        assert "image/jpeg" in formats
        assert "application/pdf" in formats


class TestTesseractOCRService:
    """Test Tesseract OCR service implementation."""
    
    def test_tesseract_initialization(self):
        """Test Tesseract service can be initialized."""
        try:
            service = TesseractOCRService(
                language="eng",
                confidence_threshold=0.8
            )
            assert service.language == "eng"
            assert service.confidence_threshold == 0.8
        except OCRError as e:
            # Skip test if pytesseract is not installed
            if "not installed" in str(e):
                pytest.skip("pytesseract not installed")
            raise
    
    def test_tesseract_default_initialization(self):
        """Test Tesseract service uses config defaults."""
        try:
            service = TesseractOCRService()
            assert service.language is not None
            assert service.confidence_threshold is not None
        except OCRError as e:
            # Skip test if pytesseract is not installed
            if "not installed" in str(e):
                pytest.skip("pytesseract not installed")
            raise
    
    def test_tesseract_extract_text_simple_image(self):
        """Test Tesseract extracts text from a simple image."""
        try:
            service = TesseractOCRService()
        except OCRError as e:
            # Skip test if pytesseract is not installed
            if "not installed" in str(e):
                pytest.skip("pytesseract not installed")
            raise
        
        # Create a simple test image with text
        image = Image.new('RGB', (200, 100), color='white')
        
        # Convert to bytes
        img_bytes = BytesIO()
        image.save(img_bytes, format='PNG')
        image_data = img_bytes.getvalue()
        
        document_id = uuid4()
        
        # Extract text
        result = service.extract_text(image_data, document_id)
        
        # Verify result structure
        assert isinstance(result, OCRResult)
        assert result.documentId == document_id
        assert isinstance(result.rawText, str)
        assert 0.0 <= result.confidence <= 1.0
        assert result.processingTime > 0
        assert result.metadata["ocrEngine"] == "tesseract"
        assert result.metadata["language"] == service.language
        assert result.metadata["imageSize"] == len(image_data)
        assert "imageDimensions" in result.metadata
    
    def test_tesseract_get_supported_formats(self):
        """Test Tesseract service returns supported formats."""
        try:
            service = TesseractOCRService()
        except OCRError as e:
            # Skip test if pytesseract is not installed
            if "not installed" in str(e):
                pytest.skip("pytesseract not installed")
            raise
        
        formats = service.get_supported_formats()
        
        assert isinstance(formats, list)
        assert len(formats) > 0
        assert "image/png" in formats
        assert "image/jpeg" in formats
        assert "image/tiff" in formats
    
    def test_tesseract_extract_text_invalid_image(self):
        """Test Tesseract handles invalid image data."""
        try:
            service = TesseractOCRService()
        except OCRError as e:
            # Skip test if pytesseract is not installed
            if "not installed" in str(e):
                pytest.skip("pytesseract not installed")
            raise
        
        document_id = uuid4()
        invalid_data = b"not an image"
        
        with pytest.raises(OCRError) as exc_info:
            service.extract_text(invalid_data, document_id)
        
        assert "Failed to extract text" in str(exc_info.value)


class TestOCRServiceFactory:
    """Test OCR service factory."""
    
    def test_factory_creates_mock_service(self, monkeypatch):
        """Test factory creates mock service when configured."""
        # Mock the settings to return 'mock' provider
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="mock")
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        service = OCRServiceFactory.create_service(enable_rate_limiting=False)
        assert isinstance(service, MockOCRService)
    
    def test_factory_creates_tesseract_service(self, monkeypatch):
        """Test factory creates Tesseract service when configured."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="tesseract")
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        try:
            service = OCRServiceFactory.create_service()
            assert isinstance(service, TesseractOCRService)
        except OCRError as e:
            # Skip test if pytesseract is not installed
            if "not installed" in str(e):
                pytest.skip("pytesseract not installed")
            raise
    
    def test_factory_raises_for_unsupported_provider(self, monkeypatch):
        """Test factory raises error for unsupported provider."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="unsupported")
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        with pytest.raises(ValueError) as exc_info:
            OCRServiceFactory.create_service()
        
        assert "Unsupported OCR provider" in str(exc_info.value)
    
    def test_factory_raises_for_unimplemented_aws(self, monkeypatch):
        """Test factory raises NotImplementedError for AWS provider."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="aws")
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        with pytest.raises(NotImplementedError) as exc_info:
            OCRServiceFactory.create_service()
        
        assert "AWS Textract not yet implemented" in str(exc_info.value)
    
    def test_factory_raises_for_unimplemented_google(self, monkeypatch):
        """Test factory raises NotImplementedError for Google provider."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="google")
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        with pytest.raises(NotImplementedError) as exc_info:
            OCRServiceFactory.create_service()
        
        assert "Google Vision API not yet implemented" in str(exc_info.value)


class TestOCRResultFields:
    """Test that OCR results contain all required fields."""
    
    def test_ocr_result_has_all_required_fields(self):
        """Test OCRResult contains all required fields per Requirement 2.5."""
        service = MockOCRService()
        document_id = uuid4()
        image_data = b"test data"
        
        result = service.extract_text(image_data, document_id)
        
        # Verify all required fields from design
        assert hasattr(result, 'documentId')
        assert hasattr(result, 'rawText')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'processingTime')
        assert hasattr(result, 'metadata')
        
        # Verify field types
        assert isinstance(result.documentId, type(document_id))
        assert isinstance(result.rawText, str)
        assert isinstance(result.confidence, float)
        assert isinstance(result.processingTime, float)
        assert isinstance(result.metadata, dict)
        
        # Verify confidence is in valid range
        assert 0.0 <= result.confidence <= 1.0
        
        # Verify processing time is positive
        assert result.processingTime > 0



class TestRateLimitedOCRService:
    """Test rate-limited OCR service wrapper."""
    
    def test_initialization_with_default_rate(self):
        """Test rate-limited service uses config default rate."""
        base_service = MockOCRService()
        service = RateLimitedOCRService(base_service)
        
        assert service.service == base_service
        assert service.rate_limiter is not None
        assert service.rate_limiter.rate > 0
    
    def test_initialization_with_custom_rate(self):
        """Test rate-limited service can use custom rate."""
        base_service = MockOCRService()
        service = RateLimitedOCRService(base_service, rate_limit=5.0)
        
        assert service.rate_limiter.rate == 5.0
    
    def test_initialization_with_timeout(self):
        """Test rate-limited service can be initialized with timeout."""
        base_service = MockOCRService()
        service = RateLimitedOCRService(base_service, rate_limit=10.0, timeout=2.0)
        
        assert service.timeout == 2.0
    
    def test_extract_text_with_rate_limiting(self):
        """Test text extraction respects rate limits."""
        base_service = MockOCRService(mock_text="Test text")
        service = RateLimitedOCRService(base_service, rate_limit=10.0)
        
        document_id = uuid4()
        image_data = b"test image"
        
        # First request should succeed
        result = service.extract_text(image_data, document_id)
        assert result.rawText == "Test text"
    
    def test_rate_limit_enforcement(self):
        """Test rate limiter enforces request limits."""
        base_service = MockOCRService(mock_text="Test text")
        # Set very low rate limit for testing
        service = RateLimitedOCRService(base_service, rate_limit=2.0)
        
        document_id = uuid4()
        image_data = b"test image"
        
        # Make requests up to the limit
        start = time.time()
        for _ in range(4):
            service.extract_text(image_data, document_id)
        elapsed = time.time() - start
        
        # Should have taken at least 1 second (4 requests at 2/sec = 2 sec, minus initial burst)
        # Allow tolerance for timing
        assert elapsed >= 0.8
    
    def test_rate_limit_timeout(self):
        """Test rate limiter respects timeout."""
        base_service = MockOCRService(mock_text="Test text")
        # Set very low rate limit and short timeout
        service = RateLimitedOCRService(base_service, rate_limit=1.0, timeout=0.1)
        
        document_id = uuid4()
        image_data = b"test image"
        
        # First request succeeds
        service.extract_text(image_data, document_id)
        
        # Second request should timeout
        from src.exceptions import OCRError
        with pytest.raises(OCRRateLimitError) as exc_info:
            service.extract_text(image_data, document_id)
        
        # Check that it's a rate limit error
        assert "timeout exceeded" in str(exc_info.value).lower()
        assert "timeout" in str(exc_info.value)
    
    def test_get_supported_formats(self):
        """Test rate-limited service delegates format query."""
        base_service = MockOCRService()
        service = RateLimitedOCRService(base_service, rate_limit=10.0)
        
        formats = service.get_supported_formats()
        assert formats == base_service.get_supported_formats()
    
    def test_get_available_tokens(self):
        """Test getting available rate limit tokens."""
        base_service = MockOCRService()
        service = RateLimitedOCRService(base_service, rate_limit=10.0)
        
        # Initially should have full capacity
        tokens = service.get_available_tokens()
        assert tokens == 10.0
        
        # After one request, should have consumed a token (allow for timing)
        document_id = uuid4()
        service.extract_text(b"test", document_id)
        tokens = service.get_available_tokens()
        assert 8.9 <= tokens <= 10.0  # Allow for timing variations
    
    def test_reset_rate_limiter(self):
        """Test resetting the rate limiter."""
        base_service = MockOCRService()
        service = RateLimitedOCRService(base_service, rate_limit=5.0)
        
        document_id = uuid4()
        
        # Make some requests
        for _ in range(3):
            service.extract_text(b"test", document_id)
        
        # Should have consumed tokens (allow for timing variations)
        tokens = service.get_available_tokens()
        assert 1.5 <= tokens <= 4.0  # Wider range for timing
        
        # Reset
        service.reset_rate_limiter()
        tokens_after_reset = service.get_available_tokens()
        assert tokens_after_reset >= 4.5  # Should be close to 5
    
    def test_ocr_error_propagation(self):
        """Test OCR errors are propagated through rate limiter."""
        # Create a mock service that raises an error
        base_service = MockOCRService()
        
        # Monkey-patch to raise error
        original_extract = base_service.extract_text
        def error_extract(image_data, document_id):
            raise OCRError("Test error")
        base_service.extract_text = error_extract
        
        service = RateLimitedOCRService(base_service, rate_limit=10.0)
        
        document_id = uuid4()
        with pytest.raises(OCRError) as exc_info:
            service.extract_text(b"test", document_id)
        
        assert "Test error" in str(exc_info.value)


class TestOCRServiceFactoryWithRateLimiting:
    """Test OCR service factory with rate limiting."""
    
    def test_factory_creates_rate_limited_service_by_default(self, monkeypatch):
        """Test factory creates rate-limited service by default."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="mock", ocr_rate_limit=10)
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        service = OCRServiceFactory.create_service()
        assert isinstance(service, RateLimitedOCRService)
        assert isinstance(service.service, MockOCRService)
    
    def test_factory_can_disable_rate_limiting(self, monkeypatch):
        """Test factory can create service without rate limiting."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="mock")
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        service = OCRServiceFactory.create_service(enable_rate_limiting=False)
        assert isinstance(service, MockOCRService)
        assert not isinstance(service, RateLimitedOCRService)
    
    def test_factory_applies_rate_limit_from_config(self, monkeypatch):
        """Test factory uses rate limit from configuration."""
        from config.settings import OCRSettings, Settings
        
        mock_settings = Settings()
        mock_settings.ocr = OCRSettings(ocr_provider="mock", ocr_rate_limit=15)
        
        monkeypatch.setattr(
            "src.ocr_service.get_settings",
            lambda: mock_settings
        )
        
        service = OCRServiceFactory.create_service()
        assert isinstance(service, RateLimitedOCRService)
        assert service.rate_limiter.rate == 15.0

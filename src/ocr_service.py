"""OCR service abstraction layer for OCR Document Extraction System

This module provides an abstract OCR interface and concrete implementations
for extracting text from document images using optical character recognition.

Supports:
- Tesseract OCR
- Confidence score calculation
- Processing time tracking
"""

import time
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Optional
from uuid import UUID

from config.settings import get_settings
from src.exceptions import OCRError
from src.models import OCRResult
from src.rate_limiter import get_ocr_rate_limiter, RateLimiter


class OCRServiceInterface(ABC):
    """Abstract interface for OCR operations.
    
    This interface defines the contract for all OCR implementations,
    ensuring consistent behavior across different OCR providers.
    """
    
    @abstractmethod
    def extract_text(self, image_data: bytes, document_id: UUID) -> OCRResult:
        """Extract text from an image using OCR.
        
        Args:
            image_data: Binary image data to process
            document_id: Unique identifier of the source document
            
        Returns:
            OCRResult containing extracted text, confidence score, and metadata
            
        Raises:
            OCRError: If text extraction fails
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Get list of supported image formats.
        
        Returns:
            List of supported MIME types
        """
        pass


class TesseractOCRService(OCRServiceInterface):
    """Tesseract OCR implementation.
    
    This implementation uses pytesseract to extract text from images.
    Tesseract is an open-source OCR engine that supports multiple languages.
    
    Attributes:
        language: OCR language code (e.g., 'eng' for English)
        confidence_threshold: Minimum confidence threshold for results
    """
    
    def __init__(
        self,
        language: Optional[str] = None,
        confidence_threshold: Optional[float] = None
    ):
        """Initialize Tesseract OCR service.
        
        Args:
            language: OCR language code (uses config if not provided)
            confidence_threshold: Minimum confidence threshold (uses config if not provided)
        """
        settings = get_settings()
        
        self.language = language or settings.ocr.ocr_language
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else settings.ocr.ocr_confidence_threshold
        )
        
        # Try to import pytesseract
        try:
            import pytesseract
            from PIL import Image
            self._pytesseract = pytesseract
            self._Image = Image
        except ImportError as e:
            raise OCRError(
                "pytesseract or PIL not installed. "
                "Install with: pip install pytesseract pillow"
            ) from e
    
    def extract_text(self, image_data: bytes, document_id: UUID) -> OCRResult:
        """Extract text from an image using Tesseract OCR.
        
        Args:
            image_data: Binary image data to process
            document_id: Unique identifier of the source document
            
        Returns:
            OCRResult containing extracted text, confidence score, and metadata
            
        Raises:
            OCRError: If text extraction fails
        """
        # Apply rate limiting
        rate_limiter = get_ocr_rate_limiter()
        rate_limiter.acquire()
        
        try:
            # Start timing
            start_time = time.time()
            
            # Load image from bytes
            image = self._Image.open(BytesIO(image_data))
            
            # Extract text using Tesseract
            raw_text = self._pytesseract.image_to_string(
                image,
                lang=self.language
            )
            
            # Get detailed OCR data for confidence calculation
            ocr_data = self._pytesseract.image_to_data(
                image,
                lang=self.language,
                output_type=self._pytesseract.Output.DICT
            )
            
            # Calculate average confidence score
            confidence = self._calculate_confidence(ocr_data)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Build metadata
            metadata = {
                "ocrEngine": "tesseract",
                "language": self.language,
                "imageSize": len(image_data),
                "imageFormat": image.format or "unknown",
                "imageDimensions": f"{image.width}x{image.height}"
            }
            
            # Create OCR result
            return OCRResult(
                documentId=document_id,
                rawText=raw_text,
                confidence=confidence,
                processingTime=processing_time,
                metadata=metadata
            )
            
        except Exception as e:
            raise OCRError(f"Failed to extract text: {str(e)}") from e
    
    def _calculate_confidence(self, ocr_data: dict) -> float:
        """Calculate average confidence score from Tesseract OCR data.
        
        Args:
            ocr_data: Dictionary containing OCR data from Tesseract
            
        Returns:
            Average confidence score between 0.0 and 1.0
        """
        # Extract confidence values (filter out -1 which indicates no text)
        confidences = [
            conf for conf in ocr_data.get('conf', [])
            if conf != -1
        ]
        
        if not confidences:
            # No text detected, return 0.0 confidence
            return 0.0
        
        # Calculate average confidence and normalize to 0.0-1.0 range
        # Tesseract confidence is 0-100, so divide by 100
        avg_confidence = sum(confidences) / len(confidences) / 100.0
        
        # Clamp to valid range
        return max(0.0, min(1.0, avg_confidence))
    
    def get_supported_formats(self) -> list[str]:
        """Get list of supported image formats.
        
        Returns:
            List of supported MIME types
        """
        return [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/tiff",
            "image/bmp",
            "image/gif"
        ]


class MockOCRService(OCRServiceInterface):
    """Mock OCR implementation for testing.
    
    This implementation returns predefined text without actually performing OCR.
    Useful for testing and development when OCR dependencies are not available.
    
    Attributes:
        mock_text: Text to return for all OCR requests
        mock_confidence: Confidence score to return
    """
    
    def __init__(
        self,
        mock_text: str = "Mock OCR extracted text",
        mock_confidence: float = 0.95
    ):
        """Initialize mock OCR service.
        
        Args:
            mock_text: Text to return for all OCR requests
            mock_confidence: Confidence score to return (0.0 to 1.0)
        """
        self.mock_text = mock_text
        self.mock_confidence = max(0.0, min(1.0, mock_confidence))
    
    def extract_text(self, image_data: bytes, document_id: UUID) -> OCRResult:
        """Extract text using mock implementation.
        
        Args:
            image_data: Binary image data (not actually processed)
            document_id: Unique identifier of the source document
            
        Returns:
            OCRResult with mock data
            
        Raises:
            OCRError: Never raised in mock implementation
        """
        # Simulate processing time
        start_time = time.time()
        time.sleep(0.1)  # Simulate 100ms processing
        processing_time = time.time() - start_time
        
        # Build metadata
        metadata = {
            "ocrEngine": "mock",
            "language": "eng",
            "imageSize": len(image_data)
        }
        
        # Create OCR result
        return OCRResult(
            documentId=document_id,
            rawText=self.mock_text,
            confidence=self.mock_confidence,
            processingTime=processing_time,
            metadata=metadata
        )
    
    def get_supported_formats(self) -> list[str]:
        """Get list of supported image formats.
        
        Returns:
            List of all common image MIME types (mock accepts all)
        """
        return [
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/tiff",
            "image/bmp",
            "image/gif",
            "application/pdf"
        ]


class RateLimitedOCRService(OCRServiceInterface):
    """Rate-limited wrapper for OCR services.
    
    This wrapper adds rate limiting to any OCR service implementation
    to prevent exceeding service quotas. Uses a token bucket algorithm
    for smooth rate limiting with burst support.
    
    Attributes:
        service: Underlying OCR service implementation
        rate_limiter: Token bucket rate limiter instance
        timeout: Maximum time to wait for rate limit token (None = wait forever)
    """
    
    def __init__(
        self,
        service: OCRServiceInterface,
        rate_limit: Optional[float] = None,
        timeout: Optional[float] = None
    ):
        """Initialize rate-limited OCR service.
        
        Args:
            service: Underlying OCR service to wrap
            rate_limit: Maximum requests per second (uses config if not provided)
            timeout: Maximum time to wait for rate limit token in seconds
        """
        self.service = service
        self.timeout = timeout
        
        # Get rate limit from config if not provided
        if rate_limit is None:
            settings = get_settings()
            rate_limit = float(settings.ocr.ocr_rate_limit)
        
        # Create token bucket rate limiter
        self.rate_limiter = RateLimiter(
            rate=rate_limit,
            capacity=int(rate_limit)  # Allow bursts up to rate
        )
    
    def extract_text(self, image_data: bytes, document_id: UUID) -> OCRResult:
        """Extract text from an image with rate limiting.
        
        This method enforces rate limits before calling the underlying
        OCR service. If the rate limit is exceeded, it will wait until
        a token becomes available (up to the configured timeout).
        
        Args:
            image_data: Binary image data to process
            document_id: Unique identifier of the source document
            
        Returns:
            OCRResult containing extracted text, confidence score, and metadata
            
        Raises:
            OCRError: If text extraction fails or rate limit timeout is exceeded
        """
        # Acquire rate limit token
        acquired = self.rate_limiter.acquire(blocking=True, timeout=self.timeout)
        
        if not acquired:
            raise OCRError(
                f"Rate limit exceeded: could not acquire token within {self.timeout}s timeout"
            )
        
        # Call underlying service
        return self.service.extract_text(image_data, document_id)
    
    def get_supported_formats(self) -> list[str]:
        """Get list of supported image formats from underlying service.
        
        Returns:
            List of supported MIME types
        """
        return self.service.get_supported_formats()
    
    def get_available_tokens(self) -> float:
        """Get the current number of available rate limit tokens.
        
        Returns:
            Number of available tokens
        """
        return self.rate_limiter.get_available_tokens()
    
    def reset_rate_limiter(self) -> None:
        """Reset the rate limiter to full capacity.
        
        This is primarily useful for testing.
        """
        self.rate_limiter.reset()


class OCRServiceFactory:
    """Factory for creating OCR service instances based on configuration.
    
    This factory creates the appropriate OCR implementation based on
    the ocr_provider configuration setting and wraps it with rate limiting.
    """
    
    @staticmethod
    def create_service(enable_rate_limiting: bool = True) -> OCRServiceInterface:
        """Create an OCR service instance based on configuration.
        
        Args:
            enable_rate_limiting: If True, wrap service with rate limiting
        
        Returns:
            OCR service implementation instance (optionally rate-limited)
            
        Raises:
            ValueError: If OCR provider is not supported
        """
        settings = get_settings()
        provider = settings.ocr.ocr_provider.lower()
        
        # Create base service
        if provider == "tesseract":
            service = TesseractOCRService()
        elif provider == "mock":
            service = MockOCRService()
        elif provider == "aws":
            # TODO: Implement AWS Textract adapter
            raise NotImplementedError("AWS Textract not yet implemented")
        elif provider == "google":
            # TODO: Implement Google Vision API adapter
            raise NotImplementedError("Google Vision API not yet implemented")
        else:
            raise ValueError(f"Unsupported OCR provider: {provider}")
        
        # Wrap with rate limiting if enabled
        if enable_rate_limiting:
            service = RateLimitedOCRService(service)
        
        return service

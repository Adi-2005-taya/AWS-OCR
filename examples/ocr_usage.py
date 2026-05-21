"""Example usage of OCR service abstraction

This example demonstrates how to use the OCR service to extract text from images.
"""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image

from src.ocr_service import OCRServiceFactory, MockOCRService, TesseractOCRService


def example_mock_ocr():
    """Example using mock OCR service for testing."""
    print("=== Mock OCR Service Example ===\n")
    
    # Create mock OCR service
    service = MockOCRService(
        mock_text="Sample invoice text\nTotal: $100.00",
        mock_confidence=0.92
    )
    
    # Simulate image data
    image_data = b"fake image bytes"
    document_id = uuid4()
    
    # Extract text
    result = service.extract_text(image_data, document_id)
    
    print(f"Document ID: {result.documentId}")
    print(f"Extracted Text: {result.rawText}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Processing Time: {result.processingTime:.3f}s")
    print(f"Metadata: {result.metadata}")
    print()


def example_factory_ocr():
    """Example using OCR service factory (uses config settings)."""
    print("=== OCR Service Factory Example ===\n")
    
    # Create OCR service from factory (uses config/settings.py)
    # Default is 'tesseract' but will fall back to mock if not installed
    try:
        service = OCRServiceFactory.create_service()
        print(f"Created service: {service.__class__.__name__}")
    except Exception as e:
        print(f"Error creating service: {e}")
        print("Falling back to mock service")
        service = MockOCRService()
    
    # Create a simple test image
    image = Image.new('RGB', (400, 200), color='white')
    
    # Convert to bytes
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    image_data = img_bytes.getvalue()
    
    document_id = uuid4()
    
    # Extract text
    result = service.extract_text(image_data, document_id)
    
    print(f"Document ID: {result.documentId}")
    print(f"Extracted Text: {result.rawText[:100]}...")  # First 100 chars
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Processing Time: {result.processingTime:.3f}s")
    print(f"OCR Engine: {result.metadata.get('ocrEngine')}")
    print()


def example_tesseract_ocr():
    """Example using Tesseract OCR service directly."""
    print("=== Tesseract OCR Service Example ===\n")
    
    try:
        # Create Tesseract service with custom settings
        service = TesseractOCRService(
            language="eng",
            confidence_threshold=0.7
        )
        
        print(f"Language: {service.language}")
        print(f"Confidence Threshold: {service.confidence_threshold}")
        print(f"Supported Formats: {', '.join(service.get_supported_formats())}")
        
        # Create a simple test image
        image = Image.new('RGB', (400, 200), color='white')
        
        # Convert to bytes
        img_bytes = BytesIO()
        image.save(img_bytes, format='PNG')
        image_data = img_bytes.getvalue()
        
        document_id = uuid4()
        
        # Extract text
        result = service.extract_text(image_data, document_id)
        
        print(f"\nDocument ID: {result.documentId}")
        print(f"Extracted Text: {result.rawText[:100] if result.rawText else '(empty)'}...")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Processing Time: {result.processingTime:.3f}s")
        print(f"Image Dimensions: {result.metadata.get('imageDimensions')}")
        
    except Exception as e:
        print(f"Tesseract not available: {e}")
        print("Install with: pip install pytesseract pillow")
        print("Also install Tesseract OCR: https://github.com/tesseract-ocr/tesseract")
    
    print()


def example_supported_formats():
    """Example showing supported image formats."""
    print("=== Supported Image Formats ===\n")
    
    service = MockOCRService()
    formats = service.get_supported_formats()
    
    print("Supported MIME types:")
    for fmt in formats:
        print(f"  - {fmt}")
    print()


if __name__ == "__main__":
    # Run all examples
    example_mock_ocr()
    example_factory_ocr()
    example_tesseract_ocr()
    example_supported_formats()
    
    print("=== Examples Complete ===")

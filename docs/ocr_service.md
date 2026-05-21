# OCR Service Abstraction

## Overview

The OCR service abstraction provides a flexible interface for extracting text from document images using optical character recognition (OCR). The implementation follows the same pattern as the storage abstraction, with an abstract interface and concrete implementations for different OCR providers.

## Architecture

### Components

1. **OCRServiceInterface** - Abstract base class defining the OCR contract
2. **TesseractOCRService** - Concrete implementation using Tesseract OCR
3. **MockOCRService** - Mock implementation for testing
4. **OCRServiceFactory** - Factory for creating OCR service instances

### Class Diagram

```
OCRServiceInterface (ABC)
├── extract_text(image_data, document_id) -> OCRResult
└── get_supported_formats() -> list[str]

TesseractOCRService (OCRServiceInterface)
├── __init__(language, confidence_threshold)
├── extract_text(image_data, document_id) -> OCRResult
├── _calculate_confidence(ocr_data) -> float
└── get_supported_formats() -> list[str]

MockOCRService (OCRServiceInterface)
├── __init__(mock_text, mock_confidence)
├── extract_text(image_data, document_id) -> OCRResult
└── get_supported_formats() -> list[str]

OCRServiceFactory
└── create_service() -> OCRServiceInterface
```

## Features

### 1. Abstract Interface

The `OCRServiceInterface` defines the contract that all OCR implementations must follow:

- `extract_text(image_data: bytes, document_id: UUID) -> OCRResult`
  - Extracts text from image data
  - Returns OCRResult with all required fields
  
- `get_supported_formats() -> list[str]`
  - Returns list of supported MIME types

### 2. Tesseract Implementation

The `TesseractOCRService` uses pytesseract to perform OCR:

**Features:**
- Multi-language support (configurable via `ocr_language` setting)
- Confidence score calculation (average of word-level confidences)
- Processing time tracking
- Detailed metadata (image size, format, dimensions)
- Error handling with descriptive messages

**Requirements:**
- `pytesseract` Python package
- `pillow` (PIL) for image processing
- Tesseract OCR engine installed on system

**Configuration:**
```python
# config/settings.py
ocr_provider = "tesseract"
ocr_language = "eng"  # Language code
ocr_confidence_threshold = 0.7  # Minimum confidence
```

### 3. Mock Implementation

The `MockOCRService` provides a testing implementation:

**Features:**
- Returns predefined text without actual OCR
- Configurable mock text and confidence
- Simulates processing time (100ms)
- Useful for testing and development

**Configuration:**
```python
# config/settings.py
ocr_provider = "mock"
```

### 4. Factory Pattern

The `OCRServiceFactory` creates the appropriate OCR service based on configuration:

```python
from src.ocr_service import OCRServiceFactory

# Creates service based on config/settings.py
service = OCRServiceFactory.create_service()
```

## Usage Examples

### Basic Usage

```python
from uuid import uuid4
from src.ocr_service import OCRServiceFactory

# Create service from factory
service = OCRServiceFactory.create_service()

# Read image file
with open('document.png', 'rb') as f:
    image_data = f.read()

# Extract text
document_id = uuid4()
result = service.extract_text(image_data, document_id)

print(f"Text: {result.rawText}")
print(f"Confidence: {result.confidence:.2%}")
print(f"Processing Time: {result.processingTime:.3f}s")
```

### Using Specific Implementation

```python
from src.ocr_service import TesseractOCRService, MockOCRService

# Use Tesseract directly
tesseract = TesseractOCRService(
    language="eng",
    confidence_threshold=0.8
)

# Use mock for testing
mock = MockOCRService(
    mock_text="Test document content",
    mock_confidence=0.95
)
```

### Checking Supported Formats

```python
service = OCRServiceFactory.create_service()
formats = service.get_supported_formats()

print("Supported formats:")
for fmt in formats:
    print(f"  - {fmt}")
```

## OCRResult Model

The `extract_text` method returns an `OCRResult` object with the following fields:

```python
OCRResult(
    documentId: UUID,           # Reference to source document
    rawText: str,               # Extracted text
    confidence: float,          # Confidence score (0.0 to 1.0)
    processingTime: float,      # Processing time in seconds
    metadata: Dict[str, Any]    # Additional metadata
)
```

### Metadata Fields

**Tesseract:**
- `ocrEngine`: "tesseract"
- `language`: Language code used
- `imageSize`: Size of image data in bytes
- `imageFormat`: Image format (PNG, JPEG, etc.)
- `imageDimensions`: Image dimensions (e.g., "400x200")

**Mock:**
- `ocrEngine`: "mock"
- `language`: "eng"
- `imageSize`: Size of image data in bytes

## Configuration

OCR settings are configured in `config/settings.py`:

```python
class OCRSettings(BaseSettings):
    ocr_provider: str = "tesseract"  # Provider: tesseract, mock, aws, google
    ocr_language: str = "eng"        # Language code
    ocr_confidence_threshold: float = 0.7  # Minimum confidence
    ocr_rate_limit: int = 10         # Max requests per second
```

Environment variables can override these settings:

```bash
OCR_PROVIDER=tesseract
OCR_LANGUAGE=eng
OCR_CONFIDENCE_THRESHOLD=0.8
OCR_RATE_LIMIT=10
```

## Error Handling

The OCR service raises `OCRError` exceptions for failures:

```python
from src.exceptions import OCRError

try:
    result = service.extract_text(image_data, document_id)
except OCRError as e:
    print(f"OCR failed: {e}")
    print(f"Error code: {e.error_code}")
    print(f"Details: {e.details}")
```

## Testing

### Unit Tests

Run OCR service tests:

```bash
pytest tests/test_ocr_service.py -v
```

### Test Coverage

The test suite covers:
- Interface contract validation
- Mock service functionality
- Tesseract service (when available)
- Factory pattern
- Confidence score calculation
- Processing time tracking
- Error handling
- OCRResult field validation

## Future Enhancements

### Planned Implementations

1. **AWS Textract Adapter**
   - Cloud-based OCR service
   - High accuracy for documents
   - Automatic table and form detection

2. **Google Vision API Adapter**
   - Cloud-based OCR service
   - Multi-language support
   - Handwriting recognition

### Configuration Example

```python
# AWS Textract
ocr_provider = "aws"
aws_region = "us-east-1"
aws_access_key_id = "..."
aws_secret_access_key = "..."

# Google Vision API
ocr_provider = "google"
google_credentials_path = "/path/to/credentials.json"
```

## Performance Considerations

### Tesseract

- Processing time varies by image size and complexity
- Typical: 1-5 seconds per page
- CPU-intensive operation
- Consider async processing for multiple documents

### Mock

- Constant processing time (~100ms)
- No actual OCR performed
- Ideal for testing and development

### Rate Limiting

Rate limiting is configured but not yet implemented (Task 6.2):

```python
ocr_rate_limit = 10  # Max requests per second
```

## Dependencies

### Required

- `pydantic>=2.0.0` - Data validation
- `python-dotenv>=1.0.0` - Configuration

### Optional (for Tesseract)

- `pytesseract>=0.3.10` - Python wrapper for Tesseract
- `pillow>=10.0.0` - Image processing

### System Requirements (for Tesseract)

- Tesseract OCR engine must be installed
- Installation guides:
  - Ubuntu: `sudo apt-get install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: Download from [GitHub](https://github.com/tesseract-ocr/tesseract)

## Related Documentation

- [Storage Abstraction](storage_abstraction.md)
- [Malware Scanning](malware_scanning.md)
- [Requirements Document](../.kiro/specs/ocr-document-extraction/requirements.md)
- [Design Document](../.kiro/specs/ocr-document-extraction/design.md)

## Requirements Validation

This implementation satisfies **Requirement 2.5**:

> WHEN the OCR_Service receives an image, THE OCR_Service SHALL extract text and return an OCR_Result with raw text, confidence score, and processing time

✅ **Implemented:**
- OCR service interface with `extract_text` method
- Concrete Tesseract adapter
- Mock adapter for testing
- Confidence score calculation
- Processing time tracking
- OCRResult with all required fields (documentId, rawText, confidence, processingTime, metadata)

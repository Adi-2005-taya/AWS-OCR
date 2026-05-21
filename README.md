# OCR Document Extraction System

An automated OCR-based document text extraction and search system that enables users to upload document images, automatically extracts text using optical character recognition, and provides full-text search capabilities.

## Features

- **Automated Document Processing**: Upload documents and automatically extract text via OCR
- **Full-Text Search**: Search across all indexed documents with relevance ranking
- **Event-Driven Architecture**: Asynchronous processing pipeline for scalability
- **Structured Logging**: Comprehensive logging with structured output
- **Error Handling**: Robust error handling with retry mechanisms
- **Security**: Encryption at rest and in transit, malware scanning, access controls

## Project Structure

```
.
├── src/                    # Source code
│   ├── __init__.py
│   ├── constants.py        # System constants and enums
│   ├── exceptions.py       # Base exception classes
│   ├── logging_config.py   # Logging configuration
│   ├── models.py           # Data models
│   └── validation.py       # Validation utilities
├── tests/                  # Test suite
│   ├── __init__.py
│   ├── test_infrastructure.py
│   ├── test_models.py
│   └── test_validation.py
├── config/                 # Configuration management
│   ├── __init__.py
│   └── settings.py         # Application settings
├── data/                   # Data directory (created at runtime)
│   └── storage/            # Local document storage
├── .env.example            # Example environment configuration
├── pyproject.toml          # Project metadata and dependencies
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Setup

### Prerequisites

- Python 3.9 or higher
- pip or poetry for dependency management

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ocr-document-extraction
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Development Setup

Install development dependencies:
```bash
pip install -e ".[dev]"
```

## Configuration

The system uses environment variables for configuration. See `.env.example` for available options.

Key configuration areas:
- **Storage**: Configure storage backend (local, S3, Azure)
- **OCR**: Configure OCR provider and settings
- **Search**: Configure search backend (in-memory, Elasticsearch)
- **Security**: Configure encryption, malware scanning, file type validation
- **Logging**: Configure log level and format

## Running Tests

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

Run property-based tests:
```bash
pytest -v -k property
```

## Architecture

The system follows an event-driven architecture with the following components:

1. **Storage Container**: Stores uploaded document images
2. **Storage Monitor**: Detects new uploads and triggers processing
3. **Document Processor**: Orchestrates the OCR workflow
4. **OCR Service**: Performs optical character recognition
5. **Text Cleaner**: Normalizes and structures extracted text
6. **Search Engine**: Indexes and queries document content
7. **Query Handler**: Processes user search requests

## Usage Examples

### File Type Validation

The system validates uploaded files against an allowlist of supported formats:

```python
from src.validation import FileTypeValidator, validate_file_type, is_valid_file_type

# Using the validator class
validator = FileTypeValidator()
validator.validate("image/png")  # Passes
validator.validate("text/plain")  # Raises InvalidFileTypeError

# Using convenience functions
validate_file_type("application/pdf")  # Passes
is_valid_file_type("image/jpeg")  # Returns True
is_valid_file_type("application/x-executable")  # Returns False

# Custom allowed types
custom_validator = FileTypeValidator(allowed_types=["image/png", "image/jpeg"])
custom_validator.validate("image/png")  # Passes
custom_validator.validate("application/pdf")  # Raises InvalidFileTypeError
```

Supported file types (configurable via `SECURITY__ALLOWED_FILE_TYPES`):
- `image/png`
- `image/jpeg`
- `image/jpg`
- `image/tiff`
- `application/pdf`

## Development

### Code Style

The project uses:
- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Run formatters and linters:
```bash
black src tests
ruff check src tests
mypy src
```

### Adding New Components

1. Create module in `src/`
2. Add tests in `tests/`
3. Update configuration in `config/settings.py` if needed
4. Document in this README

## License

[Add license information]

## Contributing

[Add contribution guidelines]

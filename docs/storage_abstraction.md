# Storage Abstraction Layer

## Overview

The storage abstraction layer provides a unified interface for storing, retrieving, and deleting document images in the DocuSense system. It supports multiple storage backends and includes built-in encryption at rest.

## Architecture

### Components

1. **StorageInterface** - Abstract base class defining the storage contract
2. **LocalFileSystemStorage** - Concrete implementation for local filesystem storage
3. **StorageFactory** - Factory for creating storage instances based on configuration
4. **Document ID Generation** - UUID v4 generation for unique document identification

### Design Principles

- **Abstraction**: Storage operations are defined through an abstract interface, allowing easy addition of new storage backends (S3, Azure Blob, etc.)
- **Encryption**: Optional encryption at rest using Fernet symmetric encryption
- **Scalability**: Directory sharding for efficient filesystem organization
- **Configuration-driven**: Storage type and settings are configured via environment variables

## Storage Interface

The `StorageInterface` abstract class defines the following operations:

```python
class StorageInterface(ABC):
    def upload(self, file_data: BinaryIO, filename: str, 
               content_type: str, document_id: Optional[UUID] = None) -> tuple[UUID, str]:
        """Upload a document to storage."""
        
    def download(self, document_id: UUID) -> bytes:
        """Download a document from storage."""
        
    def delete(self, document_id: UUID) -> bool:
        """Delete a document from storage."""
        
    def exists(self, document_id: UUID) -> bool:
        """Check if a document exists in storage."""
        
    def get_url(self, document_id: UUID) -> str:
        """Get the storage URL for a document."""
```

## Local Filesystem Storage

### Features

- **Directory Sharding**: Documents are organized into subdirectories based on the first two characters of their UUID for efficient filesystem organization
- **Encryption at Rest**: Optional Fernet symmetric encryption for stored documents
- **Automatic Cleanup**: Empty shard directories are removed when the last document is deleted
- **File URL Generation**: Returns `file://` URLs for local storage paths

### Configuration

Configure via environment variables or `.env` file:

```bash
# Storage type (local, s3, azure)
STORAGE__STORAGE_TYPE=local

# Local storage path
STORAGE__STORAGE_PATH=./data/storage

# Enable encryption at rest
STORAGE__ENCRYPTION_ENABLED=true
```

### Directory Structure

Documents are stored with directory sharding:

```
data/storage/
├── 4e/
│   └── 4e44b336-94b5-4440-9f07-28791982aa45
├── a8/
│   └── a86c9bb4-c568-418e-b71a-e3c4e56e99bc
└── 2c/
    └── 2c934665-6d79-453c-b219-0b08896d9ec6
```

## Usage Examples

### Basic Upload and Download

```python
from src.storage import StorageFactory
import io

# Create storage instance
storage = StorageFactory.create_storage()

# Upload a document
file_data = io.BytesIO(b"Document content")
document_id, storage_url = storage.upload(
    file_data=file_data,
    filename="document.txt",
    content_type="text/plain"
)

# Download the document
content = storage.download(document_id)

# Delete the document
storage.delete(document_id)
```

### With Encryption

```python
from src.storage import LocalFileSystemStorage

# Create encrypted storage
storage = LocalFileSystemStorage(
    base_path="./data/encrypted",
    encryption_enabled=True
)

# Upload (automatically encrypted)
file_data = io.BytesIO(b"Sensitive content")
document_id, storage_url = storage.upload(
    file_data=file_data,
    filename="sensitive.txt",
    content_type="text/plain"
)

# Download (automatically decrypted)
content = storage.download(document_id)
```

### With Predefined Document ID

```python
from src.storage import StorageFactory, generate_document_id

storage = StorageFactory.create_storage()

# Generate ID beforehand
document_id = generate_document_id()

# Upload with predefined ID
file_data = io.BytesIO(b"Content")
returned_id, storage_url = storage.upload(
    file_data=file_data,
    filename="doc.txt",
    content_type="text/plain",
    document_id=document_id
)

assert returned_id == document_id
```

## Error Handling

The storage layer raises `StorageError` exceptions for error conditions:

```python
from src.exceptions import StorageError
from uuid import uuid4

try:
    # Attempt to download non-existent document
    storage.download(uuid4())
except StorageError as e:
    print(f"Error: {e}")
    # Output: Error: Document not found: <uuid>
```

### Error Scenarios

- **Upload failures**: Raises `StorageError` with details
- **Download non-existent document**: Raises `StorageError` with "Document not found"
- **Get URL for non-existent document**: Raises `StorageError` with "Document not found"
- **Delete non-existent document**: Returns `False` (does not raise exception)

## Encryption Details

### Encryption Algorithm

- **Algorithm**: Fernet (symmetric encryption)
- **Key Generation**: Automatic key generation if not provided
- **Key Storage**: In production, keys should be loaded from secure key management systems (AWS KMS, Azure Key Vault, etc.)

### Security Considerations

1. **Key Management**: The current implementation generates keys at runtime. In production:
   - Store encryption keys in a secure key management system
   - Rotate keys periodically
   - Use different keys for different environments

2. **Key Rotation**: When implementing key rotation:
   - Maintain multiple keys (current + previous)
   - Re-encrypt documents with new keys during rotation
   - Track which key was used for each document

3. **Performance**: Encryption adds overhead:
   - Small files: Negligible impact
   - Large files: Consider streaming encryption for files > 100MB

## Future Storage Backends

The abstraction layer is designed to support additional storage backends:

### AWS S3

```python
class S3Storage(StorageInterface):
    """AWS S3 storage implementation."""
    # TODO: Implement S3 operations
    # - Use boto3 for S3 operations
    # - Support server-side encryption (SSE-S3, SSE-KMS)
    # - Generate presigned URLs for downloads
```

### Azure Blob Storage

```python
class AzureBlobStorage(StorageInterface):
    """Azure Blob Storage implementation."""
    # TODO: Implement Azure Blob operations
    # - Use azure-storage-blob SDK
    # - Support Azure encryption at rest
    # - Generate SAS tokens for downloads
```

## Testing

Comprehensive unit tests are provided in `tests/test_storage.py`:

- Storage interface contract
- Upload/download/delete operations
- Encryption roundtrip
- Directory sharding
- Error handling
- Edge cases (empty files, large files, multiple documents)

Run tests:

```bash
pytest tests/test_storage.py -v
```

## Requirements Validation

This implementation satisfies the following requirements:

- **Requirement 1.1**: Document upload with unique identifier assignment
- **Requirement 9.1**: Encryption at rest for stored documents
- **Requirement 10.1**: Original file storage in Storage Container
- **Requirement 10.3**: Valid and accessible storage URLs for indexed documents

## Performance Considerations

### Directory Sharding

- **Purpose**: Avoid filesystem limitations on files per directory
- **Implementation**: First 2 characters of UUID create 256 possible shards
- **Benefit**: Distributes documents evenly across subdirectories

### Encryption Overhead

- **Small files (<1MB)**: <10ms overhead
- **Medium files (1-10MB)**: 10-100ms overhead
- **Large files (>10MB)**: Consider streaming encryption

### Scalability

- **Local filesystem**: Suitable for development and small deployments
- **Cloud storage**: Recommended for production (S3, Azure Blob)
- **Concurrent access**: Local filesystem has limitations; cloud storage scales better

## Configuration Reference

### StorageSettings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `storage_type` | string | `"local"` | Storage backend type (local, s3, azure) |
| `storage_path` | string | `"./data/storage"` | Local storage directory path |
| `storage_bucket` | string | `None` | Cloud storage bucket/container name |
| `storage_region` | string | `None` | Cloud storage region |
| `encryption_enabled` | bool | `True` | Enable encryption at rest |

### Environment Variables

```bash
STORAGE__STORAGE_TYPE=local
STORAGE__STORAGE_PATH=./data/storage
STORAGE__STORAGE_BUCKET=my-bucket
STORAGE__STORAGE_REGION=us-east-1
STORAGE__ENCRYPTION_ENABLED=true
```

## See Also

- [Configuration Management](../config/settings.py)
- [Exception Handling](../src/exceptions.py)
- [Data Models](../src/models.py)
- [Usage Examples](../examples/storage_usage.py)

"""Unit tests for storage abstraction layer

Tests cover:
- Storage interface implementation
- Local filesystem storage operations
- Encryption at rest
- Document ID generation
- Error handling
"""

import io
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from src.exceptions import StorageError
from src.storage import (
    LocalFileSystemStorage,
    StorageFactory,
    StorageInterface,
    generate_document_id,
)


class TestStorageInterface:
    """Test the storage interface contract."""
    
    def test_storage_interface_is_abstract(self):
        """Test that StorageInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            StorageInterface()


class TestLocalFileSystemStorage:
    """Test local filesystem storage implementation."""
    
    @pytest.fixture
    def temp_storage_dir(self):
        """Create a temporary directory for storage tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def storage(self, temp_storage_dir):
        """Create a local filesystem storage instance."""
        return LocalFileSystemStorage(
            base_path=temp_storage_dir,
            encryption_enabled=False
        )
    
    @pytest.fixture
    def encrypted_storage(self, temp_storage_dir):
        """Create an encrypted local filesystem storage instance."""
        return LocalFileSystemStorage(
            base_path=temp_storage_dir,
            encryption_enabled=True,
            encryption_key=Fernet.generate_key()
        )
    
    def test_upload_document(self, storage):
        """Test uploading a document to storage."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        
        # Act
        document_id, storage_url = storage.upload(file_data, filename, content_type)
        
        # Assert
        assert isinstance(document_id, UUID)
        assert storage_url.startswith("file://")
        assert storage.exists(document_id)
    
    def test_upload_with_provided_document_id(self, storage):
        """Test uploading a document with a pre-generated document ID."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        provided_id = uuid4()
        
        # Act
        document_id, storage_url = storage.upload(
            file_data, filename, content_type, document_id=provided_id
        )
        
        # Assert
        assert document_id == provided_id
        assert storage.exists(document_id)
    
    def test_download_document(self, storage):
        """Test downloading a document from storage."""
        # Arrange
        original_content = b"Test document content"
        file_data = io.BytesIO(original_content)
        filename = "test.txt"
        content_type = "text/plain"
        document_id, _ = storage.upload(file_data, filename, content_type)
        
        # Act
        downloaded_content = storage.download(document_id)
        
        # Assert
        assert downloaded_content == original_content
    
    def test_download_nonexistent_document(self, storage):
        """Test downloading a document that doesn't exist."""
        # Arrange
        nonexistent_id = uuid4()
        
        # Act & Assert
        with pytest.raises(StorageError, match="Document not found"):
            storage.download(nonexistent_id)
    
    def test_delete_document(self, storage):
        """Test deleting a document from storage."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        document_id, _ = storage.upload(file_data, filename, content_type)
        
        # Act
        result = storage.delete(document_id)
        
        # Assert
        assert result is True
        assert not storage.exists(document_id)
    
    def test_delete_nonexistent_document(self, storage):
        """Test deleting a document that doesn't exist."""
        # Arrange
        nonexistent_id = uuid4()
        
        # Act
        result = storage.delete(nonexistent_id)
        
        # Assert
        assert result is False
    
    def test_exists_returns_true_for_existing_document(self, storage):
        """Test exists() returns True for an existing document."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        document_id, _ = storage.upload(file_data, filename, content_type)
        
        # Act
        exists = storage.exists(document_id)
        
        # Assert
        assert exists is True
    
    def test_exists_returns_false_for_nonexistent_document(self, storage):
        """Test exists() returns False for a nonexistent document."""
        # Arrange
        nonexistent_id = uuid4()
        
        # Act
        exists = storage.exists(nonexistent_id)
        
        # Assert
        assert exists is False
    
    def test_get_url_for_existing_document(self, storage):
        """Test getting storage URL for an existing document."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        document_id, _ = storage.upload(file_data, filename, content_type)
        
        # Act
        storage_url = storage.get_url(document_id)
        
        # Assert
        assert storage_url.startswith("file://")
        assert str(document_id) in storage_url
    
    def test_get_url_for_nonexistent_document(self, storage):
        """Test getting storage URL for a nonexistent document."""
        # Arrange
        nonexistent_id = uuid4()
        
        # Act & Assert
        with pytest.raises(StorageError, match="Document not found"):
            storage.get_url(nonexistent_id)
    
    def test_upload_with_encryption(self, encrypted_storage):
        """Test uploading a document with encryption enabled."""
        # Arrange
        original_content = b"Sensitive document content"
        file_data = io.BytesIO(original_content)
        filename = "sensitive.txt"
        content_type = "text/plain"
        
        # Act
        document_id, storage_url = encrypted_storage.upload(
            file_data, filename, content_type
        )
        
        # Assert
        assert encrypted_storage.exists(document_id)
        
        # Verify content is encrypted on disk
        doc_path = encrypted_storage._get_document_path(document_id)
        with open(doc_path, 'rb') as f:
            stored_content = f.read()
        assert stored_content != original_content  # Content should be encrypted
    
    def test_download_with_encryption(self, encrypted_storage):
        """Test downloading a document with encryption enabled."""
        # Arrange
        original_content = b"Sensitive document content"
        file_data = io.BytesIO(original_content)
        filename = "sensitive.txt"
        content_type = "text/plain"
        document_id, _ = encrypted_storage.upload(file_data, filename, content_type)
        
        # Act
        downloaded_content = encrypted_storage.download(document_id)
        
        # Assert
        assert downloaded_content == original_content  # Should be decrypted
    
    def test_encryption_roundtrip(self, encrypted_storage):
        """Test that encryption and decryption work correctly."""
        # Arrange
        original_content = b"Test encryption roundtrip"
        file_data = io.BytesIO(original_content)
        filename = "test.txt"
        content_type = "text/plain"
        
        # Act
        document_id, _ = encrypted_storage.upload(file_data, filename, content_type)
        downloaded_content = encrypted_storage.download(document_id)
        
        # Assert
        assert downloaded_content == original_content
    
    def test_directory_sharding(self, storage, temp_storage_dir):
        """Test that documents are stored in sharded directories."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        
        # Act
        document_id, _ = storage.upload(file_data, filename, content_type)
        
        # Assert
        doc_id_str = str(document_id)
        shard_dir = doc_id_str[:2]
        expected_path = Path(temp_storage_dir) / shard_dir / doc_id_str
        assert expected_path.exists()
    
    def test_delete_cleans_up_empty_shard_directory(self, storage, temp_storage_dir):
        """Test that deleting the last document in a shard removes the shard directory."""
        # Arrange
        file_data = io.BytesIO(b"Test document content")
        filename = "test.txt"
        content_type = "text/plain"
        document_id, _ = storage.upload(file_data, filename, content_type)
        
        doc_id_str = str(document_id)
        shard_dir = Path(temp_storage_dir) / doc_id_str[:2]
        
        # Act
        storage.delete(document_id)
        
        # Assert
        assert not shard_dir.exists()
    
    def test_upload_large_file(self, storage):
        """Test uploading a large file."""
        # Arrange
        large_content = b"x" * (10 * 1024 * 1024)  # 10 MB
        file_data = io.BytesIO(large_content)
        filename = "large.bin"
        content_type = "application/octet-stream"
        
        # Act
        document_id, storage_url = storage.upload(file_data, filename, content_type)
        
        # Assert
        assert storage.exists(document_id)
        downloaded_content = storage.download(document_id)
        assert len(downloaded_content) == len(large_content)
    
    def test_upload_empty_file(self, storage):
        """Test uploading an empty file."""
        # Arrange
        file_data = io.BytesIO(b"")
        filename = "empty.txt"
        content_type = "text/plain"
        
        # Act
        document_id, storage_url = storage.upload(file_data, filename, content_type)
        
        # Assert
        assert storage.exists(document_id)
        downloaded_content = storage.download(document_id)
        assert downloaded_content == b""
    
    def test_multiple_uploads_to_same_storage(self, storage):
        """Test uploading multiple documents to the same storage instance."""
        # Arrange
        documents = [
            (b"Content 1", "doc1.txt", "text/plain"),
            (b"Content 2", "doc2.txt", "text/plain"),
            (b"Content 3", "doc3.txt", "text/plain"),
        ]
        
        # Act
        uploaded_docs = []
        for content, filename, content_type in documents:
            file_data = io.BytesIO(content)
            document_id, storage_url = storage.upload(file_data, filename, content_type)
            uploaded_docs.append((document_id, content))
        
        # Assert
        for document_id, original_content in uploaded_docs:
            assert storage.exists(document_id)
            downloaded_content = storage.download(document_id)
            assert downloaded_content == original_content


class TestStorageFactory:
    """Test storage factory."""
    
    def test_create_local_storage(self, monkeypatch, tmp_path):
        """Test creating local filesystem storage via factory."""
        # Arrange
        from config.settings import Settings, StorageSettings
        
        settings = Settings(
            storage=StorageSettings(
                storage_type="local",
                storage_path=str(tmp_path)
            )
        )
        
        # Mock get_settings to return our test settings
        import src.storage
        monkeypatch.setattr(src.storage, "get_settings", lambda: settings)
        
        # Act
        storage = StorageFactory.create_storage()
        
        # Assert
        assert isinstance(storage, LocalFileSystemStorage)
    
    def test_create_s3_storage_not_implemented(self, monkeypatch, tmp_path):
        """Test that S3 storage raises NotImplementedError."""
        # Arrange
        from config.settings import Settings, StorageSettings
        
        settings = Settings(
            storage=StorageSettings(
                storage_type="s3",
                storage_bucket="test-bucket"
            )
        )
        
        # Mock get_settings to return our test settings
        import src.storage
        monkeypatch.setattr(src.storage, "get_settings", lambda: settings)
        
        # Act & Assert
        with pytest.raises(NotImplementedError, match="S3 storage not yet implemented"):
            StorageFactory.create_storage()
    
    def test_create_azure_storage_not_implemented(self, monkeypatch, tmp_path):
        """Test that Azure storage raises NotImplementedError."""
        # Arrange
        from config.settings import Settings, StorageSettings
        
        settings = Settings(
            storage=StorageSettings(
                storage_type="azure",
                storage_bucket="test-container"
            )
        )
        
        # Mock get_settings to return our test settings
        import src.storage
        monkeypatch.setattr(src.storage, "get_settings", lambda: settings)
        
        # Act & Assert
        with pytest.raises(NotImplementedError, match="Azure Blob storage not yet implemented"):
            StorageFactory.create_storage()
    
    def test_create_unsupported_storage_type(self, monkeypatch, tmp_path):
        """Test that unsupported storage type raises ValueError."""
        # Arrange
        from config.settings import Settings, StorageSettings
        
        settings = Settings(
            storage=StorageSettings(
                storage_type="unsupported",
                storage_path=str(tmp_path)
            )
        )
        
        # Mock get_settings to return our test settings
        import src.storage
        monkeypatch.setattr(src.storage, "get_settings", lambda: settings)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported storage type: unsupported"):
            StorageFactory.create_storage()


class TestDocumentIdGeneration:
    """Test document ID generation."""
    
    def test_generate_document_id_returns_uuid(self):
        """Test that generate_document_id returns a valid UUID."""
        # Act
        document_id = generate_document_id()
        
        # Assert
        assert isinstance(document_id, UUID)
    
    def test_generate_document_id_returns_unique_ids(self):
        """Test that generate_document_id returns unique IDs."""
        # Act
        ids = [generate_document_id() for _ in range(100)]
        
        # Assert
        assert len(ids) == len(set(ids))  # All IDs should be unique
    
    def test_generated_id_is_version_4_uuid(self):
        """Test that generated IDs are version 4 UUIDs."""
        # Act
        document_id = generate_document_id()
        
        # Assert
        assert document_id.version == 4

"""Storage abstraction layer for DocuSense System

This module provides an abstract storage interface and concrete implementations
for storing, retrieving, and deleting document images.

Supports:
- Local filesystem storage
- Encryption at rest
- Unique document ID generation (UUID)
"""

import hashlib
import io
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Optional
from uuid import UUID, uuid4

from cryptography.fernet import Fernet

from config.settings import get_settings
from src.exceptions import StorageError
from src.malware_scanner import MalwareScannerFactory


class StorageInterface(ABC):
    """Abstract interface for storage operations.
    
    This interface defines the contract for all storage implementations,
    ensuring consistent behavior across different storage backends.
    """
    
    @abstractmethod
    def upload(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        document_id: Optional[UUID] = None
    ) -> tuple[UUID, str]:
        """Upload a document to storage.
        
        Args:
            file_data: Binary file data to upload
            filename: Original filename
            content_type: MIME type of the file
            document_id: Optional document ID (generates new UUID if not provided)
            
        Returns:
            Tuple of (document_id, storage_url)
            
        Raises:
            StorageError: If upload fails
        """
        pass
    
    @abstractmethod
    def download(self, document_id: UUID) -> bytes:
        """Download a document from storage.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            Binary content of the document
            
        Raises:
            StorageError: If download fails or document not found
        """
        pass
    
    @abstractmethod
    def delete(self, document_id: UUID) -> bool:
        """Delete a document from storage.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if deletion was successful, False otherwise
            
        Raises:
            StorageError: If deletion fails
        """
        pass
    
    @abstractmethod
    def exists(self, document_id: UUID) -> bool:
        """Check if a document exists in storage.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if document exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_url(self, document_id: UUID) -> str:
        """Get the storage URL for a document.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            Storage URL for the document
            
        Raises:
            StorageError: If document not found
        """
        pass


class LocalFileSystemStorage(StorageInterface):
    """Local filesystem storage implementation with optional encryption.
    
    This implementation stores documents on the local filesystem with support
    for encryption at rest using Fernet symmetric encryption.
    
    Attributes:
        base_path: Base directory for document storage
        encryption_enabled: Whether encryption at rest is enabled
        _encryption_key: Fernet encryption key (if encryption enabled)
    """
    
    def __init__(
        self,
        base_path: Optional[str] = None,
        encryption_enabled: Optional[bool] = None,
        encryption_key: Optional[bytes] = None,
        malware_scanner: Optional[object] = None
    ):
        """Initialize local filesystem storage.
        
        Args:
            base_path: Base directory for storage (uses config if not provided)
            encryption_enabled: Enable encryption at rest (uses config if not provided)
            encryption_key: Encryption key for Fernet (generates new if not provided)
            malware_scanner: Malware scanner instance (creates default if not provided)
        """
        settings = get_settings()
        
        # Set base path from config or parameter
        self.base_path = Path(base_path or settings.storage.storage_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Set encryption settings
        self.encryption_enabled = (
            encryption_enabled
            if encryption_enabled is not None
            else settings.storage.encryption_enabled
        )
        
        # Initialize encryption key if encryption is enabled
        self._encryption_key: Optional[Fernet] = None
        if self.encryption_enabled:
            if encryption_key is None:
                key_path = Path("data/.storage_key")
                if key_path.exists():
                    encryption_key = key_path.read_bytes()
                else:
                    encryption_key = Fernet.generate_key()
                    key_path.parent.mkdir(parents=True, exist_ok=True)
                    key_path.write_bytes(encryption_key)
            self._encryption_key = Fernet(encryption_key)
        
        # Initialize malware scanner
        self.malware_scanner = (
            malware_scanner
            if malware_scanner is not None
            else MalwareScannerFactory.create_scanner()
        )
    
    def _get_document_path(self, document_id: UUID) -> Path:
        """Get the filesystem path for a document.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            Path object for the document file
        """
        # Use first two characters of UUID for directory sharding
        doc_id_str = str(document_id)
        shard_dir = doc_id_str[:2]
        
        # Create shard directory if it doesn't exist
        shard_path = self.base_path / shard_dir
        shard_path.mkdir(exist_ok=True)
        
        return shard_path / doc_id_str
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using Fernet encryption.
        
        Args:
            data: Raw data to encrypt
            
        Returns:
            Encrypted data
        """
        if not self.encryption_enabled or self._encryption_key is None:
            return data
        return self._encryption_key.encrypt(data)
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data using Fernet encryption.
        
        Args:
            data: Encrypted data
            
        Returns:
            Decrypted data
        """
        if not self.encryption_enabled or self._encryption_key is None:
            return data
        return self._encryption_key.decrypt(data)
    
    def upload(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        document_id: Optional[UUID] = None
    ) -> tuple[UUID, str]:
        """Upload a document to local filesystem storage.
        
        Args:
            file_data: Binary file data to upload
            filename: Original filename
            content_type: MIME type of the file
            document_id: Optional document ID (generates new UUID if not provided)
            
        Returns:
            Tuple of (document_id, storage_url)
            
        Raises:
            StorageError: If upload fails
            MalwareDetectedError: If malware is detected in the file
        """
        from src.exceptions import MalwareDetectedError
        
        try:
            # Scan for malware before accepting upload
            self.malware_scanner.scan(file_data, filename)
            
            # Generate document ID if not provided
            if document_id is None:
                document_id = uuid4()
            
            # Get storage path
            doc_path = self._get_document_path(document_id)
            
            # Read file data
            file_content = file_data.read()
            
            # Encrypt if enabled
            if self.encryption_enabled:
                file_content = self._encrypt_data(file_content)
            
            # Write to filesystem
            with open(doc_path, 'wb') as f:
                f.write(file_content)
            
            # Generate storage URL
            storage_url = self.get_url(document_id)
            
            return document_id, storage_url
        
        except MalwareDetectedError:
            # Re-raise malware detection errors without wrapping
            raise
        except Exception as e:
            raise StorageError(f"Failed to upload document: {str(e)}") from e
    
    def download(self, document_id: UUID) -> bytes:
        """Download a document from local filesystem storage.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            Binary content of the document
            
        Raises:
            StorageError: If download fails or document not found
        """
        try:
            doc_path = self._get_document_path(document_id)
            
            if not doc_path.exists():
                raise StorageError(f"Document not found: {document_id}")
            
            # Read file content
            with open(doc_path, 'rb') as f:
                file_content = f.read()
            
            # Decrypt if enabled
            if self.encryption_enabled:
                file_content = self._decrypt_data(file_content)
            
            return file_content
            
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to download document: {str(e)}") from e
    
    def delete(self, document_id: UUID) -> bool:
        """Delete a document from local filesystem storage.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if deletion was successful, False otherwise
            
        Raises:
            StorageError: If deletion fails
        """
        try:
            doc_path = self._get_document_path(document_id)
            
            if not doc_path.exists():
                return False
            
            # Delete the file
            doc_path.unlink()
            
            # Clean up empty shard directory
            shard_dir = doc_path.parent
            if shard_dir.exists() and not any(shard_dir.iterdir()):
                shard_dir.rmdir()
            
            return True
            
        except Exception as e:
            raise StorageError(f"Failed to delete document: {str(e)}") from e
    
    def exists(self, document_id: UUID) -> bool:
        """Check if a document exists in local filesystem storage.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if document exists, False otherwise
        """
        doc_path = self._get_document_path(document_id)
        return doc_path.exists()
    
    def get_url(self, document_id: UUID) -> str:
        """Get the storage URL for a document.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            Storage URL for the document (file:// URL for local storage)
            
        Raises:
            StorageError: If document not found
        """
        doc_path = self._get_document_path(document_id)
        
        if not doc_path.exists():
            raise StorageError(f"Document not found: {document_id}")
        
        # Return file:// URL
        return f"file://{doc_path.absolute()}"


class StorageFactory:
    """Factory for creating storage instances based on configuration.
    
    This factory creates the appropriate storage implementation based on
    the storage_type configuration setting.
    """
    
    @staticmethod
    def create_storage() -> StorageInterface:
        """Create a storage instance based on configuration.
        
        Returns:
            Storage implementation instance
            
        Raises:
            ValueError: If storage type is not supported
        """
        settings = get_settings()
        storage_type = settings.storage.storage_type.lower()
        
        if storage_type == "local":
            return LocalFileSystemStorage()
        elif storage_type == "s3":
            # TODO: Implement S3 storage adapter
            raise NotImplementedError("S3 storage not yet implemented")
        elif storage_type == "azure":
            # TODO: Implement Azure Blob storage adapter
            raise NotImplementedError("Azure Blob storage not yet implemented")
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")


def generate_document_id() -> UUID:
    """Generate a unique document ID.
    
    Returns:
        New UUID for document identification
    """
    return uuid4()

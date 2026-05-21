"""Example usage of the storage abstraction layer

This example demonstrates how to use the storage interface for
uploading, downloading, and deleting documents.
"""

import io
import sys
from pathlib import Path
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage import (
    LocalFileSystemStorage,
    StorageFactory,
    generate_document_id,
)


def example_basic_usage():
    """Basic storage operations example."""
    print("=== Basic Storage Usage ===\n")
    
    # Create storage instance using factory (uses config settings)
    storage = StorageFactory.create_storage()
    
    # Upload a document
    file_content = b"This is a test document with some content."
    file_data = io.BytesIO(file_content)
    
    document_id, storage_url = storage.upload(
        file_data=file_data,
        filename="test_document.txt",
        content_type="text/plain"
    )
    
    print(f"Uploaded document:")
    print(f"  ID: {document_id}")
    print(f"  URL: {storage_url}\n")
    
    # Check if document exists
    exists = storage.exists(document_id)
    print(f"Document exists: {exists}\n")
    
    # Download the document
    downloaded_content = storage.download(document_id)
    print(f"Downloaded content: {downloaded_content.decode('utf-8')}\n")
    
    # Delete the document
    deleted = storage.delete(document_id)
    print(f"Document deleted: {deleted}")
    print(f"Document exists after deletion: {storage.exists(document_id)}\n")


def example_with_encryption():
    """Storage with encryption enabled."""
    print("=== Storage with Encryption ===\n")
    
    # Create storage with encryption enabled
    storage = LocalFileSystemStorage(
        base_path="./data/encrypted_storage",
        encryption_enabled=True
    )
    
    # Upload sensitive document
    sensitive_content = b"This is sensitive information that should be encrypted."
    file_data = io.BytesIO(sensitive_content)
    
    document_id, storage_url = storage.upload(
        file_data=file_data,
        filename="sensitive.txt",
        content_type="text/plain"
    )
    
    print(f"Uploaded encrypted document:")
    print(f"  ID: {document_id}")
    print(f"  URL: {storage_url}\n")
    
    # Download and verify content is decrypted
    downloaded_content = storage.download(document_id)
    print(f"Downloaded (decrypted) content: {downloaded_content.decode('utf-8')}\n")
    
    # Clean up
    storage.delete(document_id)


def example_with_predefined_id():
    """Upload with a predefined document ID."""
    print("=== Upload with Predefined ID ===\n")
    
    storage = StorageFactory.create_storage()
    
    # Generate document ID beforehand
    predefined_id = generate_document_id()
    print(f"Generated document ID: {predefined_id}\n")
    
    # Upload with the predefined ID
    file_data = io.BytesIO(b"Document with predefined ID")
    
    document_id, storage_url = storage.upload(
        file_data=file_data,
        filename="predefined.txt",
        content_type="text/plain",
        document_id=predefined_id
    )
    
    print(f"Uploaded document:")
    print(f"  ID: {document_id}")
    print(f"  Matches predefined ID: {document_id == predefined_id}\n")
    
    # Clean up
    storage.delete(document_id)


def example_multiple_documents():
    """Upload and manage multiple documents."""
    print("=== Multiple Documents ===\n")
    
    storage = StorageFactory.create_storage()
    
    # Upload multiple documents
    documents = [
        (b"First document content", "doc1.txt"),
        (b"Second document content", "doc2.txt"),
        (b"Third document content", "doc3.txt"),
    ]
    
    uploaded_ids = []
    
    for content, filename in documents:
        file_data = io.BytesIO(content)
        document_id, storage_url = storage.upload(
            file_data=file_data,
            filename=filename,
            content_type="text/plain"
        )
        uploaded_ids.append(document_id)
        print(f"Uploaded {filename}: {document_id}")
    
    print(f"\nTotal documents uploaded: {len(uploaded_ids)}\n")
    
    # Verify all documents exist
    for doc_id in uploaded_ids:
        exists = storage.exists(doc_id)
        print(f"Document {doc_id} exists: {exists}")
    
    # Clean up all documents
    print("\nCleaning up...")
    for doc_id in uploaded_ids:
        storage.delete(doc_id)
    
    print("All documents deleted.\n")


def example_error_handling():
    """Error handling examples."""
    print("=== Error Handling ===\n")
    
    storage = StorageFactory.create_storage()
    
    # Try to download non-existent document
    try:
        non_existent_id = uuid4()
        storage.download(non_existent_id)
    except Exception as e:
        print(f"Expected error when downloading non-existent document:")
        print(f"  {type(e).__name__}: {e}\n")
    
    # Try to get URL for non-existent document
    try:
        non_existent_id = uuid4()
        storage.get_url(non_existent_id)
    except Exception as e:
        print(f"Expected error when getting URL for non-existent document:")
        print(f"  {type(e).__name__}: {e}\n")
    
    # Delete non-existent document (returns False, doesn't raise)
    non_existent_id = uuid4()
    result = storage.delete(non_existent_id)
    print(f"Deleting non-existent document returns: {result}\n")


if __name__ == "__main__":
    # Run all examples
    example_basic_usage()
    example_with_encryption()
    example_with_predefined_id()
    example_multiple_documents()
    example_error_handling()
    
    print("=== All examples completed ===")

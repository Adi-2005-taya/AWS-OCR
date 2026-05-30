"""Search engine abstraction for DocuSense System

This module provides an abstract search interface and concrete implementations
for indexing and querying document content.

Requirements: 4.1, 5.3
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from config.settings import get_settings
from src.exceptions import IndexingError, SearchError
from src.models import IndexedDocument


class SearchResult:
    """Search result data structure.
    
    Attributes:
        document_id: Unique identifier of the matched document
        score: Relevance score (higher is more relevant)
        snippet: Text snippet showing match context
        metadata: Additional result metadata
    """
    
    def __init__(
        self,
        document_id: UUID,
        score: float,
        snippet: str = "",
        metadata: Optional[Dict] = None
    ):
        """Initialize search result.
        
        Args:
            document_id: Document identifier
            score: Relevance score
            snippet: Text snippet
            metadata: Additional metadata
        """
        self.document_id = document_id
        self.score = score
        self.snippet = snippet
        self.metadata = metadata or {}
    
    def __repr__(self) -> str:
        return f"SearchResult(document_id={self.document_id}, score={self.score})"


class SearchEngineInterface(ABC):
    """Abstract interface for search operations.
    
    This interface defines the contract for all search engine implementations,
    ensuring consistent behavior across different search backends.
    """
    
    @abstractmethod
    def index(self, document: IndexedDocument) -> None:
        """Index a document for search.
        
        Args:
            document: Document to index
            
        Raises:
            IndexingError: If indexing fails
        """
        pass
    
    @abstractmethod
    def index_batch(self, documents: List[IndexedDocument]) -> None:
        """Index multiple documents in batch.
        
        Args:
            documents: List of documents to index
            
        Raises:
            IndexingError: If batch indexing fails
        """
        pass
    
    @abstractmethod
    def query(self, keywords: List[str], limit: int = 10) -> List[SearchResult]:
        """Query the search index.
        
        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results to return
            
        Returns:
            List of search results ranked by relevance
            
        Raises:
            SearchError: If query fails
        """
        pass
    
    @abstractmethod
    def delete(self, document_id: UUID) -> bool:
        """Delete a document from the search index.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if document was deleted, False if not found
            
        Raises:
            SearchError: If deletion fails
        """
        pass
    
    @abstractmethod
    def exists(self, document_id: UUID) -> bool:
        """Check if a document exists in the index.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if document exists, False otherwise
        """
        pass


class InMemorySearchEngine(SearchEngineInterface):
    """In-memory search engine implementation.
    
    This implementation stores documents in memory and performs simple
    keyword-based search with TF-IDF-like relevance scoring.
    
    Suitable for development and small deployments. For production,
    use Elasticsearch or similar.
    
    Attributes:
        documents: Dictionary mapping document IDs to indexed documents
        inverted_index: Inverted index mapping keywords to document IDs
    """
    
    def __init__(self):
        """Initialize in-memory search engine."""
        self.documents: Dict[UUID, IndexedDocument] = {}
        self.inverted_index: Dict[str, set[UUID]] = {}
        self.db_path = Path("data/search_index.json")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()
        
    def _save_to_disk(self) -> None:
        """Save the current search index to disk."""
        data = {
            "documents": {str(k): v.model_dump(mode='json') for k, v in self.documents.items()},
            "inverted_index": {k: [str(uid) for uid in v] for k, v in self.inverted_index.items()}
        }
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
    def _load_from_disk(self) -> None:
        """Load the search index from disk if it exists."""
        if not self.db_path.exists():
            return
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            docs = data.get("documents", {})
            self.documents = {UUID(k): IndexedDocument(**v) for k, v in docs.items()}
            
            inv_idx = data.get("inverted_index", {})
            self.inverted_index = {k: set(UUID(uid) for uid in v) for k, v in inv_idx.items()}
        except Exception as e:
            pass # Failsafe: if JSON is corrupt, start fresh
    
    def index(self, document: IndexedDocument) -> None:
        """Index a document for search.
        
        Args:
            document: Document to index
            
        Raises:
            IndexingError: If indexing fails
        """
        try:
            # Store document
            self.documents[document.documentId] = document
            
            # Update inverted index with keywords
            for keyword in document.keywords:
                if keyword not in self.inverted_index:
                    self.inverted_index[keyword] = set()
                self.inverted_index[keyword].add(document.documentId)
            
            # Also index words from searchable content
            words = document.searchableContent.lower().split()
            for word in words:
                if len(word) >= 3:  # Only index words with 3+ characters
                    if word not in self.inverted_index:
                        self.inverted_index[word] = set()
                    self.inverted_index[word].add(document.documentId)
            self._save_to_disk()
                    
        except Exception as e:
            raise IndexingError(
                f"Failed to index document {document.documentId}: {str(e)}",
                error_code="INDEX_FAILED",
                details={"document_id": str(document.documentId), "error": str(e)}
            ) from e
    
    def index_batch(self, documents: List[IndexedDocument]) -> None:
        """Index multiple documents in batch.
        
        Args:
            documents: List of documents to index
            
        Raises:
            IndexingError: If batch indexing fails
        """
        try:
            for document in documents:
                self.index(document)
            self._save_to_disk()
        except IndexingError:
            raise
        except Exception as e:
            raise IndexingError(
                f"Failed to batch index documents: {str(e)}",
                error_code="BATCH_INDEX_FAILED",
                details={"document_count": len(documents), "error": str(e)}
            ) from e
    
    def query(self, keywords: List[str], limit: int = 10) -> List[SearchResult]:
        """Query the search index.
        
        Uses simple keyword matching with frequency-based relevance scoring.
        
        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results to return
            
        Returns:
            List of search results ranked by relevance
            
        Raises:
            SearchError: If query fails
        """
        try:
            # Find documents matching any keyword
            matching_docs: Dict[UUID, int] = {}
            
            for keyword in keywords:
                keyword_lower = keyword.lower()
                if keyword_lower in self.inverted_index:
                    for doc_id in self.inverted_index[keyword_lower]:
                        matching_docs[doc_id] = matching_docs.get(doc_id, 0) + 1
            
            # Calculate relevance scores and create results
            results = []
            for doc_id, match_count in matching_docs.items():
                document = self.documents[doc_id]
                
                # Simple relevance score: number of matching keywords
                # normalized by total keywords in query
                score = match_count / len(keywords) if keywords else 0.0
                
                # Create snippet from cleaned text (first 200 chars)
                snippet = document.cleanedText[:200]
                if len(document.cleanedText) > 200:
                    snippet += "..."
                
                result = SearchResult(
                    document_id=doc_id,
                    score=score,
                    snippet=snippet,
                    metadata={
                        "keywords": document.keywords,
                        "index_timestamp": document.indexTimestamp.isoformat()
                    }
                )
                results.append(result)
            
            # Sort by relevance score (descending)
            results.sort(key=lambda r: r.score, reverse=True)
            
            # Return top results
            return results[:limit]
            
        except Exception as e:
            raise SearchError(
                f"Failed to query search index: {str(e)}",
                error_code="QUERY_FAILED",
                details={"keywords": keywords, "error": str(e)}
            ) from e
    
    def delete(self, document_id: UUID) -> bool:
        """Delete a document from the search index.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if document was deleted, False if not found
            
        Raises:
            SearchError: If deletion fails
        """
        try:
            if document_id not in self.documents:
                return False
            
            # Get document to remove from inverted index
            document = self.documents[document_id]
            
            # Remove from inverted index
            for keyword in document.keywords:
                if keyword in self.inverted_index:
                    self.inverted_index[keyword].discard(document_id)
                    # Clean up empty entries
                    if not self.inverted_index[keyword]:
                        del self.inverted_index[keyword]
            
            # Remove from searchable content index
            words = document.searchableContent.lower().split()
            for word in words:
                if word in self.inverted_index:
                    self.inverted_index[word].discard(document_id)
                    if not self.inverted_index[word]:
                        del self.inverted_index[word]
            
            # Remove document
            del self.documents[document_id]
            
            self._save_to_disk()
            return True
            
        except Exception as e:
            raise SearchError(
                f"Failed to delete document {document_id}: {str(e)}",
                error_code="DELETE_FAILED",
                details={"document_id": str(document_id), "error": str(e)}
            ) from e
    
    def exists(self, document_id: UUID) -> bool:
        """Check if a document exists in the index.
        
        Args:
            document_id: Unique identifier of the document
            
        Returns:
            True if document exists, False otherwise
        """
        return document_id in self.documents
    
    def get_document_count(self) -> int:
        """Get the number of indexed documents.
        
        Returns:
            Number of documents in the index
        """
        return len(self.documents)
    
    def clear(self) -> None:
        """Clear all documents from the index."""
        self.documents.clear()
        self.inverted_index.clear()


class PersistentSearchEngine(InMemorySearchEngine):
    """Search engine that persists the index to a JSON file on disk.

    Survives server restarts — loads existing index on startup and
    saves after every index/delete operation.
    """

    def __init__(self, index_path: str = "./data/search_index.json"):
        super().__init__()
        self._index_path = Path(index_path)
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── Persistence helpers ──────────────────────────────────────────

    def _save(self) -> None:
        """Serialize index to JSON file."""
        data = {
            "documents": {
                str(doc_id): {
                    "documentId":       str(doc.documentId),
                    "cleanedText":      doc.cleanedText,
                    "keywords":         doc.keywords,
                    "indexTimestamp":   doc.indexTimestamp.isoformat(),
                    "searchableContent": doc.searchableContent,
                    "metadata":         doc.metadata,
                    "ownerId":          doc.ownerId,
                }
                for doc_id, doc in self.documents.items()
            }
        }
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        """Load index from JSON file if it exists."""
        if not self._index_path.exists():
            return
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            for entry in data.get("documents", {}).values():
                doc = IndexedDocument(
                    documentId=UUID(entry["documentId"]),
                    cleanedText=entry["cleanedText"],
                    keywords=entry["keywords"],
                    indexTimestamp=datetime.fromisoformat(entry["indexTimestamp"]),
                    searchableContent=entry["searchableContent"],
                    metadata=entry.get("metadata", {}),
                    ownerId=entry.get("ownerId"),
                )
                super().index(doc)
        except Exception:
            pass  # Corrupt file — start fresh

    # ── Override mutating methods to auto-save ───────────────────────

    def index(self, document: IndexedDocument) -> None:
        super().index(document)
        self._save()

    def index_batch(self, documents: List[IndexedDocument]) -> None:
        super().index_batch(documents)
        self._save()

    def delete(self, document_id: UUID) -> bool:
        result = super().delete(document_id)
        if result:
            self._save()
        return result

    def clear(self) -> None:
        super().clear()
        self._save()


class SearchEngineFactory:
    """Factory for creating search engine instances based on configuration."""
    
    @staticmethod
    def create_engine() -> SearchEngineInterface:
        """Create a search engine instance based on configuration.
        
        Returns:
            Search engine implementation instance
            
        Raises:
            ValueError: If search backend is not supported
        """
        settings = get_settings()
        backend = settings.search.search_backend.lower()
        
        if backend == "memory":
            return InMemorySearchEngine()
        elif backend == "elasticsearch":
            # TODO: Implement Elasticsearch adapter
            raise NotImplementedError("Elasticsearch not yet implemented")
        else:
            raise ValueError(f"Unsupported search backend: {backend}")


def extract_keywords(text: str, max_keywords: int = 50) -> List[str]:
    """Extract keywords from text for indexing.
    
    This is a convenience function that extracts significant words
    from text for use in search indexing.
    
    Args:
        text: Text to extract keywords from
        max_keywords: Maximum number of keywords to extract
        
    Returns:
        List of keywords
    """
    from src.text_cleaner import get_text_cleaner
    
    cleaner = get_text_cleaner()
    return cleaner.extract_keywords(text, max_keywords=max_keywords)

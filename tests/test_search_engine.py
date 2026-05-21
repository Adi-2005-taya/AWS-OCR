"""Unit tests for search engine

Tests cover:
- Search engine interface
- In-memory search implementation
- Document indexing
- Batch indexing
- Query and relevance ranking
- Document deletion
- Search engine factory
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.exceptions import IndexingError, SearchError
from src.models import IndexedDocument
from src.search_engine import (
    InMemorySearchEngine,
    SearchEngineFactory,
    SearchEngineInterface,
    SearchResult,
    extract_keywords,
)


class TestSearchResult:
    """Tests for SearchResult class."""
    
    def test_search_result_creation(self):
        """Test creating a search result."""
        doc_id = uuid4()
        
        result = SearchResult(
            document_id=doc_id,
            score=0.95,
            snippet="Test snippet",
            metadata={"key": "value"}
        )
        
        assert result.document_id == doc_id
        assert result.score == 0.95
        assert result.snippet == "Test snippet"
        assert result.metadata == {"key": "value"}
    
    def test_search_result_default_values(self):
        """Test search result with default values."""
        doc_id = uuid4()
        
        result = SearchResult(document_id=doc_id, score=0.5)
        
        assert result.snippet == ""
        assert result.metadata == {}


class TestInMemorySearchEngine:
    """Tests for in-memory search engine."""
    
    def test_engine_initialization(self):
        """Test search engine can be initialized."""
        engine = InMemorySearchEngine()
        
        assert engine.get_document_count() == 0
    
    def test_index_document(self):
        """Test indexing a single document."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment customer",
            keywords=["invoice", "payment", "customer"],
            searchableContent="invoice payment customer"
        )
        
        engine.index(document)
        
        assert engine.get_document_count() == 1
        assert engine.exists(doc_id)
    
    def test_index_multiple_documents(self):
        """Test indexing multiple documents."""
        engine = InMemorySearchEngine()
        
        doc1 = IndexedDocument(
            documentId=uuid4(),
            cleanedText="invoice payment",
            keywords=["invoice", "payment"],
            searchableContent="invoice payment"
        )
        
        doc2 = IndexedDocument(
            documentId=uuid4(),
            cleanedText="receipt customer",
            keywords=["receipt", "customer"],
            searchableContent="receipt customer"
        )
        
        engine.index(doc1)
        engine.index(doc2)
        
        assert engine.get_document_count() == 2
    
    def test_query_single_keyword(self):
        """Test querying with a single keyword."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment customer",
            keywords=["invoice", "payment", "customer"],
            searchableContent="invoice payment customer"
        )
        
        engine.index(document)
        
        results = engine.query(["invoice"])
        
        assert len(results) == 1
        assert results[0].document_id == doc_id
        assert results[0].score > 0
    
    def test_query_multiple_keywords(self):
        """Test querying with multiple keywords."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment customer",
            keywords=["invoice", "payment", "customer"],
            searchableContent="invoice payment customer"
        )
        
        engine.index(document)
        
        results = engine.query(["invoice", "payment"])
        
        assert len(results) == 1
        assert results[0].score > 0
    
    def test_query_no_matches(self):
        """Test querying with no matching documents."""
        engine = InMemorySearchEngine()
        
        document = IndexedDocument(
            documentId=uuid4(),
            cleanedText="invoice payment",
            keywords=["invoice", "payment"],
            searchableContent="invoice payment"
        )
        
        engine.index(document)
        
        results = engine.query(["nonexistent"])
        
        assert len(results) == 0
    
    def test_query_relevance_ranking(self):
        """Test that results are ranked by relevance."""
        engine = InMemorySearchEngine()
        
        # Document with 2 matching keywords
        doc1_id = uuid4()
        doc1 = IndexedDocument(
            documentId=doc1_id,
            cleanedText="invoice payment customer",
            keywords=["invoice", "payment", "customer"],
            searchableContent="invoice payment customer"
        )
        
        # Document with 1 matching keyword
        doc2_id = uuid4()
        doc2 = IndexedDocument(
            documentId=doc2_id,
            cleanedText="invoice receipt",
            keywords=["invoice", "receipt"],
            searchableContent="invoice receipt"
        )
        
        engine.index(doc1)
        engine.index(doc2)
        
        results = engine.query(["invoice", "payment"])
        
        assert len(results) == 2
        # doc1 should rank higher (matches both keywords)
        assert results[0].document_id == doc1_id
        assert results[0].score > results[1].score
    
    def test_query_limit(self):
        """Test query result limit."""
        engine = InMemorySearchEngine()
        
        # Index 5 documents
        for i in range(5):
            doc = IndexedDocument(
                documentId=uuid4(),
                cleanedText=f"invoice {i}",
                keywords=["invoice"],
                searchableContent=f"invoice {i}"
            )
            engine.index(doc)
        
        results = engine.query(["invoice"], limit=3)
        
        assert len(results) == 3
    
    def test_query_snippet_generation(self):
        """Test that query results include snippets."""
        engine = InMemorySearchEngine()
        
        document = IndexedDocument(
            documentId=uuid4(),
            cleanedText="This is a test invoice with payment information",
            keywords=["invoice", "payment"],
            searchableContent="This is a test invoice with payment information"
        )
        
        engine.index(document)
        
        results = engine.query(["invoice"])
        
        assert len(results) == 1
        assert len(results[0].snippet) > 0
        assert "invoice" in results[0].snippet.lower()
    
    def test_delete_document(self):
        """Test deleting a document from the index."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment",
            keywords=["invoice", "payment"],
            searchableContent="invoice payment"
        )
        
        engine.index(document)
        assert engine.exists(doc_id)
        
        result = engine.delete(doc_id)
        
        assert result is True
        assert not engine.exists(doc_id)
        assert engine.get_document_count() == 0
    
    def test_delete_nonexistent_document(self):
        """Test deleting a document that doesn't exist."""
        engine = InMemorySearchEngine()
        
        result = engine.delete(uuid4())
        
        assert result is False
    
    def test_delete_removes_from_inverted_index(self):
        """Test that deletion removes document from inverted index."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment",
            keywords=["invoice", "payment"],
            searchableContent="invoice payment"
        )
        
        engine.index(document)
        engine.delete(doc_id)
        
        # Query should return no results
        results = engine.query(["invoice"])
        assert len(results) == 0
    
    def test_exists_returns_true_for_indexed_document(self):
        """Test exists returns True for indexed documents."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="test",
            keywords=["test"],
            searchableContent="test"
        )
        
        engine.index(document)
        
        assert engine.exists(doc_id) is True
    
    def test_exists_returns_false_for_nonexistent_document(self):
        """Test exists returns False for nonexistent documents."""
        engine = InMemorySearchEngine()
        
        assert engine.exists(uuid4()) is False
    
    def test_clear(self):
        """Test clearing all documents from the index."""
        engine = InMemorySearchEngine()
        
        # Index some documents
        for i in range(3):
            doc = IndexedDocument(
                documentId=uuid4(),
                cleanedText=f"test {i}",
                keywords=["test"],
                searchableContent=f"test {i}"
            )
            engine.index(doc)
        
        assert engine.get_document_count() == 3
        
        engine.clear()
        
        assert engine.get_document_count() == 0
    
    def test_index_batch(self):
        """Test batch indexing multiple documents."""
        engine = InMemorySearchEngine()
        
        documents = [
            IndexedDocument(
                documentId=uuid4(),
                cleanedText=f"document {i}",
                keywords=["document"],
                searchableContent=f"document {i}"
            )
            for i in range(5)
        ]
        
        engine.index_batch(documents)
        
        assert engine.get_document_count() == 5
    
    def test_query_case_insensitive(self):
        """Test that queries are case-insensitive."""
        engine = InMemorySearchEngine()
        
        document = IndexedDocument(
            documentId=uuid4(),
            cleanedText="invoice payment",
            keywords=["invoice", "payment"],
            searchableContent="invoice payment"
        )
        
        engine.index(document)
        
        # Query with different cases
        results1 = engine.query(["INVOICE"])
        results2 = engine.query(["Invoice"])
        results3 = engine.query(["invoice"])
        
        assert len(results1) == 1
        assert len(results2) == 1
        assert len(results3) == 1


class TestSearchEngineFactory:
    """Tests for search engine factory."""
    
    def test_factory_creates_memory_engine(self, monkeypatch):
        """Test factory creates in-memory engine when configured."""
        from config.settings import SearchSettings, Settings
        
        settings = Settings()
        settings.search = SearchSettings(search_backend="memory")
        
        monkeypatch.setattr("src.search_engine.get_settings", lambda: settings)
        
        engine = SearchEngineFactory.create_engine()
        
        assert isinstance(engine, InMemorySearchEngine)
    
    def test_factory_raises_for_elasticsearch(self, monkeypatch):
        """Test factory raises NotImplementedError for Elasticsearch."""
        from config.settings import SearchSettings, Settings
        
        settings = Settings()
        settings.search = SearchSettings(search_backend="elasticsearch")
        
        monkeypatch.setattr("src.search_engine.get_settings", lambda: settings)
        
        with pytest.raises(NotImplementedError):
            SearchEngineFactory.create_engine()
    
    def test_factory_raises_for_unsupported_backend(self, monkeypatch):
        """Test factory raises ValueError for unsupported backend."""
        from config.settings import SearchSettings, Settings
        
        settings = Settings()
        settings.search = SearchSettings(search_backend="unsupported")
        
        monkeypatch.setattr("src.search_engine.get_settings", lambda: settings)
        
        with pytest.raises(ValueError):
            SearchEngineFactory.create_engine()


class TestExtractKeywords:
    """Tests for extract_keywords convenience function."""
    
    def test_extract_keywords(self):
        """Test extracting keywords from text."""
        text = "invoice payment customer order"
        
        keywords = extract_keywords(text)
        
        assert "invoice" in keywords
        assert "payment" in keywords
        assert "customer" in keywords
        assert "order" in keywords


class TestSearchEngineIntegration:
    """Integration tests for search engine."""
    
    def test_complete_indexing_and_search_workflow(self):
        """Test complete workflow: index documents and search."""
        engine = InMemorySearchEngine()
        
        # Index multiple documents
        doc1_id = uuid4()
        doc1 = IndexedDocument(
            documentId=doc1_id,
            cleanedText="invoice for customer john doe",
            keywords=["invoice", "customer", "john", "doe"],
            searchableContent="invoice for customer john doe"
        )
        
        doc2_id = uuid4()
        doc2 = IndexedDocument(
            documentId=doc2_id,
            cleanedText="receipt for customer jane smith",
            keywords=["receipt", "customer", "jane", "smith"],
            searchableContent="receipt for customer jane smith"
        )
        
        doc3_id = uuid4()
        doc3 = IndexedDocument(
            documentId=doc3_id,
            cleanedText="invoice for supplier acme corp",
            keywords=["invoice", "supplier", "acme", "corp"],
            searchableContent="invoice for supplier acme corp"
        )
        
        engine.index(doc1)
        engine.index(doc2)
        engine.index(doc3)
        
        # Search for "invoice"
        results = engine.query(["invoice"])
        assert len(results) == 2
        assert doc1_id in [r.document_id for r in results]
        assert doc3_id in [r.document_id for r in results]
        
        # Search for "customer"
        results = engine.query(["customer"])
        assert len(results) == 2
        assert doc1_id in [r.document_id for r in results]
        assert doc2_id in [r.document_id for r in results]
        
        # Search for "invoice customer" (should rank doc1 highest)
        results = engine.query(["invoice", "customer"])
        assert len(results) == 3
        assert results[0].document_id == doc1_id  # Matches both keywords
    
    def test_update_document_by_reindexing(self):
        """Test updating a document by reindexing."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        # Index original document
        doc_v1 = IndexedDocument(
            documentId=doc_id,
            cleanedText="original content",
            keywords=["original"],
            searchableContent="original content"
        )
        engine.index(doc_v1)
        
        # Reindex with updated content
        doc_v2 = IndexedDocument(
            documentId=doc_id,
            cleanedText="updated content",
            keywords=["updated"],
            searchableContent="updated content"
        )
        engine.index(doc_v2)
        
        # Should find with new keyword
        results = engine.query(["updated"])
        assert len(results) == 1
        assert results[0].document_id == doc_id

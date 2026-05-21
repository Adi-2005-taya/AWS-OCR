"""Unit tests for query handler

Tests cover:
- Query tokenization
- Search engine invocation
- Result formatting with storage URLs
- Empty query handling
"""

from uuid import uuid4

import pytest

from src.exceptions import EmptyQueryError, SearchQueryError
from src.models import IndexedDocument
from src.query_handler import QueryHandler, QueryResult, create_query_handler
from src.search_engine import InMemorySearchEngine


class TestQueryResult:
    """Tests for QueryResult class."""
    
    def test_query_result_creation(self):
        """Test creating a query result."""
        doc_id = uuid4()
        
        result = QueryResult(
            document_id=doc_id,
            score=0.95,
            snippet="Test snippet",
            storage_url="file:///path/to/doc",
            metadata={"key": "value"}
        )
        
        assert result.document_id == doc_id
        assert result.score == 0.95
        assert result.snippet == "Test snippet"
        assert result.storage_url == "file:///path/to/doc"
        assert result.metadata == {"key": "value"}


class TestQueryHandler:
    """Tests for QueryHandler class."""
    
    def test_query_handler_initialization(self):
        """Test query handler can be initialized."""
        handler = QueryHandler()
        
        assert handler is not None
        assert handler.search_engine is not None
    
    def test_tokenize_query_basic(self):
        """Test tokenizing a basic query."""
        handler = QueryHandler()
        
        keywords = handler.tokenize_query("invoice payment")
        
        assert "invoice" in keywords
        assert "payment" in keywords
    
    def test_tokenize_query_case_insensitive(self):
        """Test that tokenization is case-insensitive."""
        handler = QueryHandler()
        
        keywords = handler.tokenize_query("INVOICE Payment")
        
        assert "invoice" in keywords
        assert "payment" in keywords
    
    def test_tokenize_query_filters_short_words(self):
        """Test that very short words are filtered out."""
        handler = QueryHandler()
        
        keywords = handler.tokenize_query("invoice a payment")
        
        assert "invoice" in keywords
        assert "payment" in keywords
        assert "a" not in keywords
    
    def test_tokenize_query_empty_raises_error(self):
        """Test that empty query raises EmptyQueryError."""
        handler = QueryHandler()
        
        with pytest.raises(EmptyQueryError):
            handler.tokenize_query("")
    
    def test_tokenize_query_whitespace_only_raises_error(self):
        """Test that whitespace-only query raises EmptyQueryError."""
        handler = QueryHandler()
        
        with pytest.raises(EmptyQueryError):
            handler.tokenize_query("   \n\t   ")
    
    def test_search_basic(self):
        """Test basic search functionality."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        # Index a document
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="invoice payment customer",
            keywords=["invoice", "payment", "customer"],
            searchableContent="invoice payment customer"
        )
        engine.index(document)
        
        handler = QueryHandler(search_engine=engine)
        
        results = handler.search("invoice")
        
        assert len(results) == 1
        assert results[0].document_id == doc_id
        assert results[0].storage_url is not None
    
    def test_search_with_storage_url_provider(self):
        """Test search with custom storage URL provider."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="test",
            keywords=["test"],
            searchableContent="test"
        )
        engine.index(document)
        
        def custom_url_provider(document_id):
            return f"custom://{document_id}"
        
        handler = QueryHandler(
            search_engine=engine,
            storage_url_provider=custom_url_provider
        )
        
        results = handler.search("test")
        
        assert len(results) == 1
        assert results[0].storage_url.startswith("custom://")
    
    def test_search_empty_query_raises_error(self):
        """Test that empty query raises EmptyQueryError."""
        handler = QueryHandler()
        
        with pytest.raises(EmptyQueryError):
            handler.search("")
    
    def test_search_no_results(self):
        """Test search with no matching documents."""
        engine = InMemorySearchEngine()
        handler = QueryHandler(search_engine=engine)
        
        results = handler.search("nonexistent")
        
        assert len(results) == 0
    
    def test_search_respects_limit(self):
        """Test that search respects result limit."""
        engine = InMemorySearchEngine()
        
        # Index 5 documents
        for i in range(5):
            doc = IndexedDocument(
                documentId=uuid4(),
                cleanedText=f"test {i}",
                keywords=["test"],
                searchableContent=f"test {i}"
            )
            engine.index(doc)
        
        handler = QueryHandler(search_engine=engine)
        
        results = handler.search("test", limit=3)
        
        assert len(results) == 3
    
    def test_search_includes_snippet(self):
        """Test that search results include snippets."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="This is a test invoice document",
            keywords=["invoice"],
            searchableContent="This is a test invoice document"
        )
        engine.index(document)
        
        handler = QueryHandler(search_engine=engine)
        
        results = handler.search("invoice")
        
        assert len(results) == 1
        assert len(results[0].snippet) > 0
    
    def test_search_includes_metadata(self):
        """Test that search results include metadata."""
        engine = InMemorySearchEngine()
        doc_id = uuid4()
        
        document = IndexedDocument(
            documentId=doc_id,
            cleanedText="test",
            keywords=["test"],
            searchableContent="test"
        )
        engine.index(document)
        
        handler = QueryHandler(search_engine=engine)
        
        results = handler.search("test")
        
        assert len(results) == 1
        assert isinstance(results[0].metadata, dict)


class TestCreateQueryHandler:
    """Tests for create_query_handler factory function."""
    
    def test_create_query_handler(self):
        """Test creating query handler with factory function."""
        handler = create_query_handler()
        
        assert isinstance(handler, QueryHandler)
    
    def test_create_query_handler_with_engine(self):
        """Test creating query handler with custom engine."""
        engine = InMemorySearchEngine()
        
        handler = create_query_handler(search_engine=engine)
        
        assert handler.search_engine is engine


class TestQueryHandlerIntegration:
    """Integration tests for query handler."""
    
    def test_complete_search_workflow(self):
        """Test complete search workflow."""
        engine = InMemorySearchEngine()
        
        # Index multiple documents
        doc1_id = uuid4()
        doc1 = IndexedDocument(
            documentId=doc1_id,
            cleanedText="invoice for customer john",
            keywords=["invoice", "customer", "john"],
            searchableContent="invoice for customer john"
        )
        
        doc2_id = uuid4()
        doc2 = IndexedDocument(
            documentId=doc2_id,
            cleanedText="receipt for customer jane",
            keywords=["receipt", "customer", "jane"],
            searchableContent="receipt for customer jane"
        )
        
        engine.index(doc1)
        engine.index(doc2)
        
        handler = QueryHandler(search_engine=engine)
        
        # Search for "invoice"
        results = handler.search("invoice")
        assert len(results) == 1
        assert results[0].document_id == doc1_id
        
        # Search for "customer"
        results = handler.search("customer")
        assert len(results) == 2
        
        # Search for "john"
        results = handler.search("john")
        assert len(results) == 1
        assert results[0].document_id == doc1_id



class MockAuthorizationProvider:
    """Mock authorization provider for testing."""
    
    def __init__(self, authorized_docs=None):
        """Initialize with set of authorized document IDs per user.
        
        Args:
            authorized_docs: Dict mapping user_id to set of authorized document IDs
        """
        self.authorized_docs = authorized_docs or {}
        self.authorization_checks = []
    
    def is_authorized(self, user_id: str, document_id) -> bool:
        """Check if user is authorized to access document.
        
        Args:
            user_id: User identifier
            document_id: Document identifier
            
        Returns:
            True if authorized, False otherwise
        """
        self.authorization_checks.append((user_id, document_id))
        if user_id not in self.authorized_docs:
            return False
        return document_id in self.authorized_docs[user_id]


class TestAccessControl:
    """Tests for access control functionality.
    
    Requirements: 9.3
    """
    
    def test_search_without_user_id_returns_all_results(self):
        """Test that search without user_id returns all results (no filtering)."""
        engine = InMemorySearchEngine()
        
        # Index 3 documents
        doc_ids = []
        for i in range(3):
            doc_id = uuid4()
            doc_ids.append(doc_id)
            doc = IndexedDocument(
                documentId=doc_id,
                cleanedText=f"test document {i}",
                keywords=["test"],
                searchableContent=f"test document {i}"
            )
            engine.index(doc)
        
        handler = QueryHandler(search_engine=engine)
        
        # Search without user_id
        results = handler.search("test")
        
        assert len(results) == 3
    
    def test_search_with_user_id_filters_unauthorized_documents(self):
        """Test that search with user_id filters out unauthorized documents."""
        engine = InMemorySearchEngine()
        
        # Index 3 documents
        doc1_id = uuid4()
        doc2_id = uuid4()
        doc3_id = uuid4()
        
        for doc_id in [doc1_id, doc2_id, doc3_id]:
            doc = IndexedDocument(
                documentId=doc_id,
                cleanedText="test document",
                keywords=["test"],
                searchableContent="test document"
            )
            engine.index(doc)
        
        # User is only authorized for doc1 and doc3
        auth_provider = MockAuthorizationProvider(
            authorized_docs={
                "user1": {doc1_id, doc3_id}
            }
        )
        
        handler = QueryHandler(
            search_engine=engine,
            authorization_provider=auth_provider
        )
        
        # Search with user_id
        results = handler.search("test", user_id="user1")
        
        # Should only return authorized documents
        assert len(results) == 2
        result_ids = {r.document_id for r in results}
        assert doc1_id in result_ids
        assert doc3_id in result_ids
        assert doc2_id not in result_ids
    
    def test_search_with_unauthorized_user_returns_empty(self):
        """Test that search by unauthorized user returns no results."""
        engine = InMemorySearchEngine()
        
        # Index a document
        doc_id = uuid4()
        doc = IndexedDocument(
            documentId=doc_id,
            cleanedText="test document",
            keywords=["test"],
            searchableContent="test document"
        )
        engine.index(doc)
        
        # User2 has no authorized documents
        auth_provider = MockAuthorizationProvider(
            authorized_docs={
                "user1": {doc_id}
            }
        )
        
        handler = QueryHandler(
            search_engine=engine,
            authorization_provider=auth_provider
        )
        
        # Search with unauthorized user
        results = handler.search("test", user_id="user2")
        
        assert len(results) == 0
    
    def test_search_calls_authorization_provider_for_each_result(self):
        """Test that authorization provider is called for each search result."""
        engine = InMemorySearchEngine()
        
        # Index 3 documents
        doc_ids = []
        for i in range(3):
            doc_id = uuid4()
            doc_ids.append(doc_id)
            doc = IndexedDocument(
                documentId=doc_id,
                cleanedText=f"test document {i}",
                keywords=["test"],
                searchableContent=f"test document {i}"
            )
            engine.index(doc)
        
        auth_provider = MockAuthorizationProvider(
            authorized_docs={
                "user1": set(doc_ids)
            }
        )
        
        handler = QueryHandler(
            search_engine=engine,
            authorization_provider=auth_provider
        )
        
        # Search with user_id
        results = handler.search("test", user_id="user1")
        
        # Authorization provider should be called for each document
        assert len(auth_provider.authorization_checks) == 3
        for user_id, doc_id in auth_provider.authorization_checks:
            assert user_id == "user1"
            assert doc_id in doc_ids
    
    def test_search_respects_limit_after_filtering(self):
        """Test that search respects limit after access control filtering."""
        engine = InMemorySearchEngine()
        
        # Index 10 documents
        doc_ids = []
        for i in range(10):
            doc_id = uuid4()
            doc_ids.append(doc_id)
            doc = IndexedDocument(
                documentId=doc_id,
                cleanedText=f"test document {i}",
                keywords=["test"],
                searchableContent=f"test document {i}"
            )
            engine.index(doc)
        
        # User is authorized for all documents
        auth_provider = MockAuthorizationProvider(
            authorized_docs={
                "user1": set(doc_ids)
            }
        )
        
        handler = QueryHandler(
            search_engine=engine,
            authorization_provider=auth_provider
        )
        
        # Search with limit
        results = handler.search("test", limit=5, user_id="user1")
        
        # Should return exactly 5 results
        assert len(results) == 5
    
    def test_search_requests_more_results_when_user_id_provided(self):
        """Test that search requests more results from engine when filtering is needed."""
        engine = InMemorySearchEngine()
        
        # Index 10 documents
        doc_ids = []
        for i in range(10):
            doc_id = uuid4()
            doc_ids.append(doc_id)
            doc = IndexedDocument(
                documentId=doc_id,
                cleanedText=f"test document {i}",
                keywords=["test"],
                searchableContent=f"test document {i}"
            )
            engine.index(doc)
        
        # User is authorized for only half the documents
        auth_provider = MockAuthorizationProvider(
            authorized_docs={
                "user1": set(doc_ids[:5])
            }
        )
        
        handler = QueryHandler(
            search_engine=engine,
            authorization_provider=auth_provider
        )
        
        # Search with limit=5
        results = handler.search("test", limit=5, user_id="user1")
        
        # Should return 5 authorized results
        assert len(results) == 5
        for result in results:
            assert result.document_id in doc_ids[:5]
    
    def test_default_authorization_provider_allows_all(self):
        """Test that default authorization provider allows all access."""
        from src.query_handler import DefaultAuthorizationProvider
        
        provider = DefaultAuthorizationProvider()
        
        # Should allow access to any document for any user
        assert provider.is_authorized("user1", uuid4()) is True
        assert provider.is_authorized("user2", uuid4()) is True
        assert provider.is_authorized("", uuid4()) is True
    
    def test_query_handler_uses_default_authorization_provider(self):
        """Test that QueryHandler uses default authorization provider when none provided."""
        handler = QueryHandler()
        
        from src.query_handler import DefaultAuthorizationProvider
        assert isinstance(handler.authorization_provider, DefaultAuthorizationProvider)


class TestAccessControlIntegration:
    """Integration tests for access control.
    
    Requirements: 9.3
    """
    
    def test_complete_access_control_workflow(self):
        """Test complete workflow with access control."""
        engine = InMemorySearchEngine()
        
        # Index documents for different users
        user1_doc1 = uuid4()
        user1_doc2 = uuid4()
        user2_doc1 = uuid4()
        shared_doc = uuid4()
        
        for doc_id in [user1_doc1, user1_doc2, user2_doc1, shared_doc]:
            doc = IndexedDocument(
                documentId=doc_id,
                cleanedText="invoice payment customer",
                keywords=["invoice", "payment", "customer"],
                searchableContent="invoice payment customer"
            )
            engine.index(doc)
        
        # Set up authorization
        auth_provider = MockAuthorizationProvider(
            authorized_docs={
                "user1": {user1_doc1, user1_doc2, shared_doc},
                "user2": {user2_doc1, shared_doc}
            }
        )
        
        handler = QueryHandler(
            search_engine=engine,
            authorization_provider=auth_provider
        )
        
        # User1 searches
        user1_results = handler.search("invoice", user_id="user1")
        user1_doc_ids = {r.document_id for r in user1_results}
        
        assert len(user1_results) == 3
        assert user1_doc1 in user1_doc_ids
        assert user1_doc2 in user1_doc_ids
        assert shared_doc in user1_doc_ids
        assert user2_doc1 not in user1_doc_ids
        
        # User2 searches
        user2_results = handler.search("invoice", user_id="user2")
        user2_doc_ids = {r.document_id for r in user2_results}
        
        assert len(user2_results) == 2
        assert user2_doc1 in user2_doc_ids
        assert shared_doc in user2_doc_ids
        assert user1_doc1 not in user2_doc_ids
        assert user1_doc2 not in user2_doc_ids
        
        # Search without user_id returns all
        all_results = handler.search("invoice")
        assert len(all_results) == 4

"""Query handler for DocuSense System

This module provides query processing logic for user search requests.

Requirements: 5.1, 5.2, 5.4, 5.5, 5.6, 9.3
"""

import re
from typing import List, Optional, Protocol
from uuid import UUID

from src.exceptions import EmptyQueryError, SearchQueryError
from src.search_engine import SearchEngineFactory, SearchEngineInterface, SearchResult


class AuthorizationProvider(Protocol):
    """Protocol for authorization providers.
    
    Authorization providers determine whether a user has access to a document.
    """
    
    def is_authorized(self, user_id: str, document_id: UUID) -> bool:
        """Check if user is authorized to access a document.
        
        Args:
            user_id: User identifier
            document_id: Document identifier
            
        Returns:
            True if authorized, False otherwise
        """
        ...


class DefaultAuthorizationProvider:
    """Default authorization provider that allows all access.
    
    This is a permissive default for testing and development.
    In production, replace with a real authorization implementation.
    """
    
    def is_authorized(self, user_id: str, document_id: UUID) -> bool:
        """Allow all access by default.
        
        Args:
            user_id: User identifier
            document_id: Document identifier
            
        Returns:
            Always True
        """
        return True


class QueryResult:
    """Query result with document information.
    
    Attributes:
        document_id: Document identifier
        score: Relevance score
        snippet: Text snippet
        storage_url: URL to access the original document
        metadata: Additional metadata
    """
    
    def __init__(
        self,
        document_id: UUID,
        score: float,
        snippet: str,
        storage_url: str,
        metadata: Optional[dict] = None
    ):
        self.document_id = document_id
        self.score = score
        self.snippet = snippet
        self.storage_url = storage_url
        self.metadata = metadata or {}


class QueryHandler:
    """Query handler for processing user search requests.
    
    This class tokenizes queries, invokes the search engine, and formats
    results with storage URLs.
    """
    
    def __init__(
        self,
        search_engine: Optional[SearchEngineInterface] = None,
        storage_url_provider: Optional[callable] = None,
        authorization_provider: Optional[AuthorizationProvider] = None
    ):
        """Initialize query handler.
        
        Args:
            search_engine: Search engine instance (creates default if not provided)
            storage_url_provider: Function to get storage URL for document ID
            authorization_provider: Authorization provider for access control
        """
        self.search_engine = search_engine or SearchEngineFactory.create_engine()
        self.storage_url_provider = storage_url_provider or self._default_storage_url
        self.authorization_provider = authorization_provider or DefaultAuthorizationProvider()
    
    def _default_storage_url(self, document_id: UUID) -> str:
        """Default storage URL provider.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Storage URL
        """
        return f"storage://{document_id}"
    
    def tokenize_query(self, query: str) -> List[str]:
        """Tokenize query string into keywords.
        
        Extracts words from the query, filtering out very short words
        and normalizing to lowercase.
        
        Args:
            query: Query string
            
        Returns:
            List of keywords
            
        Raises:
            EmptyQueryError: If query is empty or produces no keywords
        """
        if not query or not query.strip():
            raise EmptyQueryError(
                "Query cannot be empty",
                error_code="EMPTY_QUERY",
                details={"query": query}
            )
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter out very short words (less than 2 characters)
        keywords = [w for w in words if len(w) >= 2]
        
        if not keywords:
            raise EmptyQueryError(
                "Query produced no valid keywords",
                error_code="NO_KEYWORDS",
                details={"query": query, "words": words}
            )
        
        return keywords
    
    def search(
        self,
        query: str,
        limit: int = 10,
        user_id: Optional[str] = None
    ) -> List[QueryResult]:
        """Process search query and return results.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            user_id: Optional user ID for access control
            
        Returns:
            List of query results with storage URLs (filtered by access control)
            
        Raises:
            EmptyQueryError: If query is empty
            SearchQueryError: If search fails
        """
        try:
            # Tokenize query
            keywords = self.tokenize_query(query)
            
            # Search using search engine (request more results to account for filtering)
            # Request up to 2x limit to ensure we have enough after filtering
            search_limit = limit * 2 if user_id else limit
            search_results = self.search_engine.query(keywords, limit=search_limit)
            
            # Format results with storage URLs and apply access control
            query_results = []
            for result in search_results:
                # Apply access control if user_id is provided
                if user_id and not self.authorization_provider.is_authorized(
                    user_id, result.document_id
                ):
                    # Skip documents the user is not authorized to access
                    continue
                
                # Get storage URL for document
                storage_url = self.storage_url_provider(result.document_id)
                
                # Create query result
                query_result = QueryResult(
                    document_id=result.document_id,
                    score=result.score,
                    snippet=result.snippet,
                    storage_url=storage_url,
                    metadata=result.metadata
                )
                query_results.append(query_result)
                
                # Stop once we have enough results
                if len(query_results) >= limit:
                    break
            
            return query_results
            
        except EmptyQueryError:
            raise
        except Exception as e:
            raise SearchQueryError(
                f"Search query failed: {str(e)}",
                error_code="QUERY_FAILED",
                details={"query": query, "error": str(e)}
            ) from e


def create_query_handler(
    search_engine: Optional[SearchEngineInterface] = None
) -> QueryHandler:
    """Create a query handler instance.
    
    Args:
        search_engine: Optional search engine instance
        
    Returns:
        QueryHandler instance
    """
    return QueryHandler(search_engine=search_engine)

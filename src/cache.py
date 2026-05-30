"""Document caching layer for DocuSense System

Provides an in-memory LRU cache with TTL expiry for frequently accessed
documents, with hit/miss metrics.

Requirements: 8.4
"""

import time
import threading
import structlog
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Generic, Optional, TypeVar

from src.models import Document

logger = structlog.get_logger(__name__)

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class CacheEntry(Generic[V]):
    """A single cache entry with TTL tracking.

    Attributes:
        value: Cached value
        expires_at: Unix timestamp when this entry expires
    """

    value: V
    expires_at: float


@dataclass
class CacheMetrics:
    """Cache performance metrics.

    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        evictions: Number of entries evicted (LRU or TTL)
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total > 0 else 0.0


class LRUCache(Generic[K, V]):
    """Thread-safe LRU cache with TTL expiry.

    Evicts the least-recently-used entry when capacity is exceeded.
    Entries also expire after a configurable TTL.

    Requirements: 8.4
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600) -> None:
        """Initialize the cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live for each entry in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._lock = threading.Lock()
        self.metrics = CacheMetrics()
        self.logger = logger.bind(component="lru_cache")

    def get(self, key: K) -> Optional[V]:
        """Retrieve a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value, or None if not found / expired
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.metrics.misses += 1
                return None

            if time.monotonic() > entry.expires_at:
                # Expired — evict and report miss
                del self._store[key]
                self.metrics.evictions += 1
                self.metrics.misses += 1
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            self.metrics.hits += 1
            return entry.value

    def set(self, key: K, value: V) -> None:
        """Store a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = CacheEntry(
                value=value,
                expires_at=time.monotonic() + self.ttl_seconds,
            )

            # Evict LRU entry if over capacity
            if len(self._store) > self.max_size:
                evicted_key, _ = self._store.popitem(last=False)
                self.metrics.evictions += 1
                self.logger.debug("LRU eviction", key=str(evicted_key))

    def delete(self, key: K) -> bool:
        """Remove an entry from the cache.

        Args:
            key: Cache key

        Returns:
            True if the key existed and was removed
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Return the number of entries currently in the cache."""
        with self._lock:
            return len(self._store)

    def reset_metrics(self) -> None:
        """Reset hit/miss/eviction counters."""
        with self._lock:
            self.metrics = CacheMetrics()


class DocumentCache:
    """High-level document cache backed by LRUCache.

    Caches Document objects keyed by their UUID.

    Requirements: 8.4
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 3600) -> None:
        """Initialize the document cache.

        Args:
            max_size: Maximum number of documents to cache
            ttl_seconds: TTL for each cached document
        """
        from uuid import UUID
        self._cache: LRUCache[UUID, Document] = LRUCache(
            max_size=max_size, ttl_seconds=ttl_seconds
        )
        self.logger = logger.bind(component="document_cache")

    def get(self, document_id) -> Optional[Document]:
        """Retrieve a document from the cache.

        Args:
            document_id: Document UUID

        Returns:
            Cached Document, or None on miss/expiry
        """
        doc = self._cache.get(document_id)
        if doc is not None:
            self.logger.debug("Cache hit", document_id=str(document_id))
        else:
            self.logger.debug("Cache miss", document_id=str(document_id))
        return doc

    def set(self, document: Document) -> None:
        """Store a document in the cache.

        Args:
            document: Document to cache
        """
        self._cache.set(document.id, document)
        self.logger.debug("Cached document", document_id=str(document.id))

    def delete(self, document_id) -> bool:
        """Remove a document from the cache.

        Args:
            document_id: Document UUID

        Returns:
            True if removed
        """
        removed = self._cache.delete(document_id)
        if removed:
            self.logger.debug("Evicted document", document_id=str(document_id))
        return removed

    def clear(self) -> None:
        """Clear all cached documents."""
        self._cache.clear()

    @property
    def metrics(self) -> CacheMetrics:
        """Return cache metrics."""
        return self._cache.metrics

    def size(self) -> int:
        """Return number of cached documents."""
        return self._cache.size()


# Global instance
_document_cache: Optional[DocumentCache] = None


def get_document_cache(max_size: int = 1000, ttl_seconds: float = 3600) -> DocumentCache:
    """Get the global DocumentCache singleton.

    Args:
        max_size: Used only on first call to configure the cache
        ttl_seconds: Used only on first call to configure the cache

    Returns:
        DocumentCache singleton
    """
    global _document_cache
    if _document_cache is None:
        _document_cache = DocumentCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _document_cache


def reset_document_cache() -> None:
    """Reset the global document cache (for testing)."""
    global _document_cache
    _document_cache = None

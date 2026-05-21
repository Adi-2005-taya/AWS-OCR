"""Tests for document caching layer

Requirements: 8.4
"""

import time
from uuid import uuid4

import pytest

from src.cache import (
    CacheMetrics,
    DocumentCache,
    LRUCache,
    get_document_cache,
    reset_document_cache,
)
from src.models import Document
from src.constants import DocumentStatus


def make_document(doc_id=None) -> Document:
    return Document(
        id=doc_id or uuid4(),
        filename="test.pdf",
        storageUrl="file:///test.pdf",
        contentType="application/pdf",
        status=DocumentStatus.UPLOADED,
    )


class TestCacheMetrics:
    def test_initial_metrics(self):
        m = CacheMetrics()
        assert m.hits == 0
        assert m.misses == 0
        assert m.evictions == 0
        assert m.total == 0
        assert m.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        m = CacheMetrics(hits=3, misses=1)
        assert m.total == 4
        assert m.hit_rate == 0.75


class TestLRUCache:
    def test_set_and_get(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_missing_key_returns_none(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        assert cache.get("missing") is None

    def test_get_missing_increments_miss(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.get("missing")
        assert cache.metrics.misses == 1

    def test_get_hit_increments_hit(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.set("k", "v")
        cache.get("k")
        assert cache.metrics.hits == 1

    def test_expired_entry_returns_none(self):
        cache = LRUCache(max_size=10, ttl_seconds=0.01)
        cache.set("k", "v")
        time.sleep(0.05)
        assert cache.get("k") is None

    def test_expired_entry_increments_eviction_and_miss(self):
        cache = LRUCache(max_size=10, ttl_seconds=0.01)
        cache.set("k", "v")
        time.sleep(0.05)
        cache.get("k")
        assert cache.metrics.evictions == 1
        assert cache.metrics.misses == 1

    def test_lru_eviction_when_over_capacity(self):
        cache = LRUCache(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.metrics.evictions == 1

    def test_access_updates_lru_order(self):
        cache = LRUCache(max_size=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")       # "a" is now most recently used
        cache.set("d", 4)    # should evict "b" (now LRU)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_delete_removes_entry(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.set("k", "v")
        assert cache.delete("k") is True
        assert cache.get("k") is None

    def test_delete_missing_key_returns_false(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        assert cache.delete("missing") is False

    def test_clear_removes_all_entries(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        for i in range(5):
            cache.set(str(i), i)
        cache.clear()
        assert cache.size() == 0

    def test_size_reflects_entry_count(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        assert cache.size() == 0
        cache.set("a", 1)
        assert cache.size() == 1
        cache.set("b", 2)
        assert cache.size() == 2

    def test_reset_metrics(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.set("k", "v")
        cache.get("k")
        cache.get("missing")
        cache.reset_metrics()
        assert cache.metrics.hits == 0
        assert cache.metrics.misses == 0

    def test_overwrite_existing_key(self):
        cache = LRUCache(max_size=10, ttl_seconds=60)
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get("k") == "new"
        assert cache.size() == 1


class TestDocumentCache:
    def test_set_and_get_document(self):
        dc = DocumentCache()
        doc = make_document()
        dc.set(doc)
        result = dc.get(doc.id)
        assert result is doc

    def test_get_missing_document_returns_none(self):
        dc = DocumentCache()
        assert dc.get(uuid4()) is None

    def test_delete_document(self):
        dc = DocumentCache()
        doc = make_document()
        dc.set(doc)
        assert dc.delete(doc.id) is True
        assert dc.get(doc.id) is None

    def test_delete_missing_returns_false(self):
        dc = DocumentCache()
        assert dc.delete(uuid4()) is False

    def test_clear_removes_all(self):
        dc = DocumentCache()
        for _ in range(5):
            dc.set(make_document())
        dc.clear()
        assert dc.size() == 0

    def test_metrics_track_hits_and_misses(self):
        dc = DocumentCache()
        doc = make_document()
        dc.set(doc)
        dc.get(doc.id)       # hit
        dc.get(uuid4())      # miss
        assert dc.metrics.hits == 1
        assert dc.metrics.misses == 1

    def test_lru_eviction_respects_max_size(self):
        dc = DocumentCache(max_size=2)
        doc1 = make_document()
        doc2 = make_document()
        doc3 = make_document()
        dc.set(doc1)
        dc.set(doc2)
        dc.set(doc3)  # evicts doc1
        assert dc.get(doc1.id) is None
        assert dc.get(doc2.id) is not None
        assert dc.get(doc3.id) is not None

    def test_ttl_expiry(self):
        dc = DocumentCache(ttl_seconds=0.01)
        doc = make_document()
        dc.set(doc)
        time.sleep(0.05)
        assert dc.get(doc.id) is None


class TestGlobalDocumentCache:
    def setup_method(self):
        reset_document_cache()

    def teardown_method(self):
        reset_document_cache()

    def test_get_document_cache_returns_instance(self):
        dc = get_document_cache()
        assert isinstance(dc, DocumentCache)

    def test_get_document_cache_is_singleton(self):
        dc1 = get_document_cache()
        dc2 = get_document_cache()
        assert dc1 is dc2

    def test_reset_creates_new_instance(self):
        dc1 = get_document_cache()
        reset_document_cache()
        dc2 = get_document_cache()
        assert dc1 is not dc2


class TestDocumentCacheIntegration:
    def test_cache_hit_avoids_repeated_lookups(self):
        """Simulate caching pattern: fetch once, serve from cache."""
        dc = DocumentCache()
        doc = make_document()

        # First access — cache miss, then store
        assert dc.get(doc.id) is None
        dc.set(doc)

        # Subsequent accesses — cache hit
        for _ in range(5):
            result = dc.get(doc.id)
            assert result is doc

        assert dc.metrics.hits == 5
        assert dc.metrics.misses == 1

    def test_cache_invalidation_on_delete(self):
        """Deleting a document should invalidate its cache entry."""
        dc = DocumentCache()
        doc = make_document()
        dc.set(doc)

        dc.delete(doc.id)

        assert dc.get(doc.id) is None

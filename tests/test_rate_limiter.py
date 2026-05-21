"""Unit tests for rate limiting

Tests cover:
- Token bucket rate limiter
- OCR-specific rate limiter
- Rate limit enforcement
- Timeout handling
"""

import time
from threading import Thread

import pytest

from src.exceptions import OCRRateLimitError
from src.rate_limiter import (
    OCRRateLimiter,
    RateLimiter,
    get_ocr_rate_limiter,
    reset_ocr_rate_limiter,
)


class TestRateLimiter:
    """Tests for generic rate limiter."""
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter can be initialized."""
        limiter = RateLimiter(rate=10.0)
        
        assert limiter.rate == 10.0
        assert limiter.capacity == 10
        assert limiter.tokens == 10.0
    
    def test_rate_limiter_custom_capacity(self):
        """Test rate limiter with custom capacity."""
        limiter = RateLimiter(rate=10.0, capacity=20)
        
        assert limiter.rate == 10.0
        assert limiter.capacity == 20
        assert limiter.tokens == 20.0
    
    def test_acquire_token_success(self):
        """Test acquiring a token when available."""
        limiter = RateLimiter(rate=10.0)
        
        result = limiter.acquire(blocking=False)
        
        assert result is True
        assert limiter.tokens < 10.0
    
    def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens."""
        limiter = RateLimiter(rate=10.0, capacity=5)
        
        # Acquire 5 tokens
        for _ in range(5):
            result = limiter.acquire(blocking=False)
            assert result is True
        
        # 6th attempt should fail (non-blocking)
        result = limiter.acquire(blocking=False)
        assert result is False
    
    def test_try_acquire_non_blocking(self):
        """Test try_acquire method."""
        limiter = RateLimiter(rate=10.0, capacity=1)
        
        # First acquire should succeed
        assert limiter.try_acquire() is True
        
        # Second should fail (no tokens)
        assert limiter.try_acquire() is False
    
    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate=10.0, capacity=10)
        
        # Consume all tokens
        for _ in range(10):
            limiter.acquire(blocking=False)
        
        # No tokens available
        assert limiter.try_acquire() is False
        
        # Wait for tokens to refill (0.2 seconds = 2 tokens at 10/sec)
        time.sleep(0.2)
        
        # Should have tokens now
        assert limiter.try_acquire() is True
    
    def test_blocking_acquire_waits(self):
        """Test that blocking acquire waits for tokens."""
        limiter = RateLimiter(rate=5.0, capacity=1)
        
        # Consume the token
        limiter.acquire(blocking=False)
        
        # Blocking acquire should wait and succeed
        start = time.time()
        result = limiter.acquire(blocking=True, timeout=1.0)
        elapsed = time.time() - start
        
        assert result is True
        assert elapsed >= 0.15  # Should wait ~0.2 seconds for next token
    
    def test_acquire_timeout(self):
        """Test that acquire raises error on timeout."""
        limiter = RateLimiter(rate=1.0, capacity=1)
        
        # Consume the token
        limiter.acquire(blocking=False)
        
        # Try to acquire with short timeout
        with pytest.raises(OCRRateLimitError) as exc_info:
            limiter.acquire(blocking=True, timeout=0.1)
        
        assert "timeout exceeded" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "RATE_LIMIT_TIMEOUT"
    
    def test_get_available_tokens(self):
        """Test getting available token count."""
        limiter = RateLimiter(rate=10.0, capacity=10)
        
        # Initially full
        assert limiter.get_available_tokens() == 10.0
        
        # After consuming one
        limiter.acquire(blocking=False)
        tokens = limiter.get_available_tokens()
        assert 8.9 <= tokens <= 9.1  # Allow for small timing variations
    
    def test_reset(self):
        """Test resetting the rate limiter."""
        limiter = RateLimiter(rate=10.0, capacity=10)
        
        # Consume some tokens
        for _ in range(5):
            limiter.acquire(blocking=False)
        
        assert limiter.get_available_tokens() < 10.0
        
        # Reset
        limiter.reset()
        
        assert limiter.get_available_tokens() == 10.0
    
    def test_concurrent_access(self):
        """Test rate limiter with concurrent access."""
        limiter = RateLimiter(rate=10.0, capacity=10)
        results = []
        
        def acquire_token():
            result = limiter.try_acquire()
            results.append(result)
        
        # Create 15 threads trying to acquire tokens
        threads = [Thread(target=acquire_token) for _ in range(15)]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Only 10 should succeed (capacity is 10)
        assert sum(results) == 10


class TestOCRRateLimiter:
    """Tests for OCR-specific rate limiter."""
    
    def test_ocr_rate_limiter_initialization(self):
        """Test OCR rate limiter can be initialized."""
        limiter = OCRRateLimiter(rate_limit=10)
        
        assert limiter.rate_limit == 10
    
    def test_ocr_rate_limiter_uses_config(self, monkeypatch):
        """Test OCR rate limiter uses config settings."""
        from config.settings import OCRSettings, Settings
        
        settings = Settings()
        settings.ocr = OCRSettings(ocr_rate_limit=15)
        
        monkeypatch.setattr("src.rate_limiter.get_settings", lambda: settings)
        
        limiter = OCRRateLimiter()
        
        assert limiter.rate_limit == 15
    
    def test_ocr_acquire_success(self):
        """Test acquiring OCR permission."""
        limiter = OCRRateLimiter(rate_limit=10)
        
        # Should not raise
        limiter.acquire(timeout=1.0)
    
    def test_ocr_try_acquire(self):
        """Test try_acquire for OCR."""
        limiter = OCRRateLimiter(rate_limit=1)
        
        # First should succeed
        assert limiter.try_acquire() is True
        
        # Second should fail
        assert limiter.try_acquire() is False
    
    def test_ocr_get_available_capacity(self):
        """Test getting available OCR capacity."""
        limiter = OCRRateLimiter(rate_limit=10)
        
        capacity = limiter.get_available_capacity()
        
        assert capacity == 10.0
    
    def test_ocr_reset(self):
        """Test resetting OCR rate limiter."""
        limiter = OCRRateLimiter(rate_limit=10)
        
        # Consume some capacity
        for _ in range(5):
            limiter.try_acquire()
        
        assert limiter.get_available_capacity() < 10.0
        
        # Reset
        limiter.reset()
        
        assert limiter.get_available_capacity() == 10.0
    
    def test_ocr_acquire_timeout(self):
        """Test OCR acquire with timeout."""
        limiter = OCRRateLimiter(rate_limit=1)
        
        # Consume capacity
        limiter.try_acquire()
        
        # Try to acquire with short timeout
        with pytest.raises(OCRRateLimitError):
            limiter.acquire(timeout=0.1)


class TestGlobalOCRRateLimiter:
    """Tests for global OCR rate limiter."""
    
    def test_get_ocr_rate_limiter_singleton(self):
        """Test that get_ocr_rate_limiter returns singleton."""
        reset_ocr_rate_limiter()
        
        limiter1 = get_ocr_rate_limiter()
        limiter2 = get_ocr_rate_limiter()
        
        assert limiter1 is limiter2
    
    def test_reset_ocr_rate_limiter(self):
        """Test resetting global rate limiter."""
        limiter1 = get_ocr_rate_limiter()
        
        reset_ocr_rate_limiter()
        
        limiter2 = get_ocr_rate_limiter()
        
        assert limiter1 is not limiter2


class TestRateLimiterIntegration:
    """Integration tests for rate limiting."""
    
    def test_rate_limiting_enforces_limit(self):
        """Test that rate limiting actually enforces the limit."""
        limiter = RateLimiter(rate=5.0, capacity=5)
        
        # Acquire 5 tokens quickly
        start = time.time()
        for _ in range(5):
            limiter.acquire(blocking=False)
        elapsed = time.time() - start
        
        # Should be very fast (no waiting)
        assert elapsed < 0.1
        
        # Next 5 should require waiting
        start = time.time()
        for _ in range(5):
            limiter.acquire(blocking=True, timeout=2.0)
        elapsed = time.time() - start
        
        # Should take ~1 second (5 tokens at 5/sec)
        assert elapsed >= 0.8
    
    def test_burst_capacity(self):
        """Test that burst capacity works correctly."""
        limiter = RateLimiter(rate=2.0, capacity=10)
        
        # Should be able to acquire 10 tokens immediately (burst)
        start = time.time()
        for _ in range(10):
            result = limiter.acquire(blocking=False)
            assert result is True
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should be instant
        
        # 11th should fail
        assert limiter.try_acquire() is False

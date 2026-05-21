"""Rate limiting for OCR Document Extraction System

This module provides rate limiting functionality to prevent exceeding service quotas.
Uses a token bucket algorithm for smooth rate limiting.

Requirements: 8.3
"""

import asyncio
import threading
import time
from typing import Optional

from config.settings import get_settings
from src.exceptions import OCRRateLimitError


class RateLimiter:
    """Token bucket rate limiter implementation.
    
    This rate limiter uses the token bucket algorithm to limit the rate of operations.
    Tokens are added to the bucket at a constant rate, and each operation consumes one token.
    If no tokens are available, the operation is blocked until a token becomes available.
    
    Attributes:
        rate: Maximum number of operations per second
        capacity: Maximum number of tokens in the bucket
        tokens: Current number of available tokens
        last_update: Timestamp of last token update
    """
    
    def __init__(self, rate: float, capacity: Optional[int] = None):
        """Initialize rate limiter.
        
        Args:
            rate: Maximum operations per second
            capacity: Maximum burst capacity (defaults to rate if not provided)
        """
        self.rate = rate
        self.capacity = capacity or int(rate)
        self.tokens = float(self.capacity)
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire a token from the rate limiter.
        
        Args:
            blocking: If True, block until a token is available
            timeout: Maximum time to wait for a token (only used if blocking=True)
            
        Returns:
            True if token was acquired, False otherwise
            
        Raises:
            OCRRateLimitError: If timeout is exceeded while waiting for token
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                self._refill_tokens()
                
                if self.tokens >= 1.0:
                    # Token available, consume it
                    self.tokens -= 1.0
                    return True
                
                if not blocking:
                    # Non-blocking mode, return immediately
                    return False
                
                # Calculate wait time for next token
                wait_time = (1.0 - self.tokens) / self.rate
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise OCRRateLimitError(
                        f"Rate limit timeout exceeded after {elapsed:.2f}s",
                        error_code="RATE_LIMIT_TIMEOUT",
                        details={
                            "rate": self.rate,
                            "timeout": timeout,
                            "elapsed": elapsed
                        }
                    )
                wait_time = min(wait_time, timeout - elapsed)
            
            # Wait for next token
            time.sleep(wait_time)
    
    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.
        
        Returns:
            True if token was acquired, False otherwise
        """
        return self.acquire(blocking=False)
    
    def get_available_tokens(self) -> float:
        """Get the current number of available tokens.
        
        Returns:
            Number of available tokens
        """
        with self._lock:
            self._refill_tokens()
            return self.tokens
    
    def reset(self) -> None:
        """Reset the rate limiter to full capacity."""
        with self._lock:
            self.tokens = float(self.capacity)
            self.last_update = time.time()


class OCRRateLimiter:
    """Rate limiter specifically for OCR operations.
    
    This class wraps the generic RateLimiter with OCR-specific configuration
    and error handling.
    """
    
    def __init__(self, rate_limit: Optional[int] = None):
        """Initialize OCR rate limiter.
        
        Args:
            rate_limit: Maximum OCR requests per second (uses config if not provided)
        """
        settings = get_settings()
        self.rate_limit = rate_limit or settings.ocr.ocr_rate_limit
        self._limiter = RateLimiter(rate=float(self.rate_limit))
    
    def acquire(self, timeout: Optional[float] = 30.0) -> None:
        """Acquire permission to make an OCR request.
        
        Args:
            timeout: Maximum time to wait (default: 30 seconds)
            
        Raises:
            OCRRateLimitError: If rate limit is exceeded or timeout occurs
        """
        try:
            self._limiter.acquire(blocking=True, timeout=timeout)
        except OCRRateLimitError:
            raise
    
    def try_acquire(self) -> bool:
        """Try to acquire permission without blocking.
        
        Returns:
            True if permission granted, False if rate limit would be exceeded
        """
        return self._limiter.try_acquire()
    
    def get_available_capacity(self) -> float:
        """Get the current available capacity.
        
        Returns:
            Number of requests that can be made immediately
        """
        return self._limiter.get_available_tokens()
    
    def reset(self) -> None:
        """Reset the rate limiter."""
        self._limiter.reset()


# Global OCR rate limiter instance
_ocr_rate_limiter: Optional[OCRRateLimiter] = None


def get_ocr_rate_limiter() -> OCRRateLimiter:
    """Get the global OCR rate limiter instance.
    
    Returns:
        OCR rate limiter instance
    """
    global _ocr_rate_limiter
    if _ocr_rate_limiter is None:
        _ocr_rate_limiter = OCRRateLimiter()
    return _ocr_rate_limiter


def reset_ocr_rate_limiter() -> None:
    """Reset the global OCR rate limiter instance."""
    global _ocr_rate_limiter
    _ocr_rate_limiter = None

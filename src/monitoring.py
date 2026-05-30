"""Monitoring and observability for DocuSense System

Provides metrics collection and health check endpoints for all
external dependencies.

Requirements: 7.1, 7.2, 7.3, 8.1, 8.3, 8.4
"""

import time
import structlog
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class Metrics:
    """System-wide metrics counters.

    Attributes:
        upload_count: Total documents uploaded
        processing_success_count: Documents successfully processed
        processing_failure_count: Documents that failed processing
        ocr_call_count: Total OCR service calls
        ocr_success_count: Successful OCR calls
        ocr_failure_count: Failed OCR calls
        total_ocr_processing_time: Cumulative OCR processing time (seconds)
        search_query_count: Total search queries
        total_search_latency: Cumulative search latency (seconds)
        cache_hits: Cache hit count
        cache_misses: Cache miss count
        indexing_retry_count: Documents queued for indexing retry
    """

    upload_count: int = 0
    processing_success_count: int = 0
    processing_failure_count: int = 0
    ocr_call_count: int = 0
    ocr_success_count: int = 0
    ocr_failure_count: int = 0
    total_ocr_processing_time: float = 0.0
    search_query_count: int = 0
    total_search_latency: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    indexing_retry_count: int = 0

    # --- Derived properties ---

    @property
    def ocr_success_rate(self) -> float:
        return self.ocr_success_count / self.ocr_call_count if self.ocr_call_count else 0.0

    @property
    def avg_ocr_processing_time(self) -> float:
        return (
            self.total_ocr_processing_time / self.ocr_success_count
            if self.ocr_success_count
            else 0.0
        )

    @property
    def avg_search_latency(self) -> float:
        return (
            self.total_search_latency / self.search_query_count
            if self.search_query_count
            else 0.0
        )

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total else 0.0


class MetricsCollector:
    """Thread-safe metrics collector.

    Requirements: 8.1, 8.3, 8.4
    """

    def __init__(self) -> None:
        self._metrics = Metrics()
        self.logger = logger.bind(component="metrics_collector")

    @property
    def metrics(self) -> Metrics:
        return self._metrics

    def record_upload(self) -> None:
        self._metrics.upload_count += 1

    def record_processing_success(self) -> None:
        self._metrics.processing_success_count += 1

    def record_processing_failure(self) -> None:
        self._metrics.processing_failure_count += 1

    def record_ocr_call(self, success: bool, processing_time: float = 0.0) -> None:
        self._metrics.ocr_call_count += 1
        if success:
            self._metrics.ocr_success_count += 1
            self._metrics.total_ocr_processing_time += processing_time
        else:
            self._metrics.ocr_failure_count += 1

    def record_search_query(self, latency_seconds: float) -> None:
        self._metrics.search_query_count += 1
        self._metrics.total_search_latency += latency_seconds

    def record_cache_hit(self) -> None:
        self._metrics.cache_hits += 1

    def record_cache_miss(self) -> None:
        self._metrics.cache_misses += 1

    def record_indexing_retry(self) -> None:
        self._metrics.indexing_retry_count += 1

    def reset(self) -> None:
        self._metrics = Metrics()


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckResult:
    """Result of a single health check.

    Attributes:
        name: Component name
        healthy: Whether the component is healthy
        message: Human-readable status message
        latency_ms: Check latency in milliseconds
    """

    name: str
    healthy: bool
    message: str
    latency_ms: float = 0.0


@dataclass
class HealthStatus:
    """Aggregated health status for the whole system.

    Attributes:
        healthy: True only if all checks pass
        checks: Individual check results
    """

    healthy: bool
    checks: List[HealthCheckResult] = field(default_factory=list)


class HealthChecker:
    """Runs health checks against all registered dependencies.

    Requirements: 7.1, 7.2, 7.3
    """

    def __init__(self) -> None:
        self._checks: Dict[str, Callable[[], bool]] = {}
        self.logger = logger.bind(component="health_checker")

    def register(self, name: str, check_fn: Callable[[], bool]) -> None:
        """Register a health check function.

        Args:
            name: Component name (e.g., "storage", "search_engine")
            check_fn: Zero-argument callable returning True if healthy
        """
        self._checks[name] = check_fn

    def check_all(self) -> HealthStatus:
        """Run all registered health checks.

        Returns:
            HealthStatus with individual results and overall health
        """
        results: List[HealthCheckResult] = []

        for name, fn in self._checks.items():
            start = time.monotonic()
            try:
                healthy = fn()
                latency_ms = (time.monotonic() - start) * 1000
                result = HealthCheckResult(
                    name=name,
                    healthy=healthy,
                    message="OK" if healthy else "UNHEALTHY",
                    latency_ms=latency_ms,
                )
            except Exception as e:
                latency_ms = (time.monotonic() - start) * 1000
                result = HealthCheckResult(
                    name=name,
                    healthy=False,
                    message=f"ERROR: {e}",
                    latency_ms=latency_ms,
                )
                self.logger.error("Health check failed", component=name, error=str(e))

            results.append(result)

        overall = all(r.healthy for r in results)
        self.logger.info(
            "Health check completed",
            healthy=overall,
            checks={r.name: r.healthy for r in results},
        )
        return HealthStatus(healthy=overall, checks=results)

    def check(self, name: str) -> Optional[HealthCheckResult]:
        """Run a single named health check.

        Args:
            name: Component name

        Returns:
            HealthCheckResult, or None if not registered
        """
        fn = self._checks.get(name)
        if fn is None:
            return None
        start = time.monotonic()
        try:
            healthy = fn()
            return HealthCheckResult(
                name=name,
                healthy=healthy,
                message="OK" if healthy else "UNHEALTHY",
                latency_ms=(time.monotonic() - start) * 1000,
            )
        except Exception as e:
            return HealthCheckResult(
                name=name,
                healthy=False,
                message=f"ERROR: {e}",
                latency_ms=(time.monotonic() - start) * 1000,
            )


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_metrics_collector: Optional[MetricsCollector] = None
_health_checker: Optional[HealthChecker] = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics_collector() -> None:
    global _metrics_collector
    _metrics_collector = None


def get_health_checker() -> HealthChecker:
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def reset_health_checker() -> None:
    global _health_checker
    _health_checker = None

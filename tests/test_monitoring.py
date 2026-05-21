"""Tests for monitoring and observability

Requirements: 7.1, 7.2, 7.3, 8.1, 8.3, 8.4
"""

import pytest

from src.monitoring import (
    HealthCheckResult,
    HealthChecker,
    HealthStatus,
    Metrics,
    MetricsCollector,
    get_health_checker,
    get_metrics_collector,
    reset_health_checker,
    reset_metrics_collector,
)


class TestMetrics:
    def test_initial_values(self):
        m = Metrics()
        assert m.upload_count == 0
        assert m.ocr_call_count == 0
        assert m.search_query_count == 0

    def test_ocr_success_rate_zero_when_no_calls(self):
        assert Metrics().ocr_success_rate == 0.0

    def test_ocr_success_rate(self):
        m = Metrics(ocr_call_count=4, ocr_success_count=3)
        assert m.ocr_success_rate == 0.75

    def test_avg_ocr_processing_time(self):
        m = Metrics(ocr_success_count=2, total_ocr_processing_time=6.0)
        assert m.avg_ocr_processing_time == 3.0

    def test_avg_search_latency(self):
        m = Metrics(search_query_count=5, total_search_latency=2.5)
        assert m.avg_search_latency == 0.5

    def test_cache_hit_rate(self):
        m = Metrics(cache_hits=3, cache_misses=1)
        assert m.cache_hit_rate == 0.75

    def test_cache_hit_rate_zero_when_no_accesses(self):
        assert Metrics().cache_hit_rate == 0.0


class TestMetricsCollector:
    def test_record_upload(self):
        mc = MetricsCollector()
        mc.record_upload()
        assert mc.metrics.upload_count == 1

    def test_record_processing_success(self):
        mc = MetricsCollector()
        mc.record_processing_success()
        assert mc.metrics.processing_success_count == 1

    def test_record_processing_failure(self):
        mc = MetricsCollector()
        mc.record_processing_failure()
        assert mc.metrics.processing_failure_count == 1

    def test_record_ocr_call_success(self):
        mc = MetricsCollector()
        mc.record_ocr_call(success=True, processing_time=1.5)
        assert mc.metrics.ocr_call_count == 1
        assert mc.metrics.ocr_success_count == 1
        assert mc.metrics.total_ocr_processing_time == 1.5

    def test_record_ocr_call_failure(self):
        mc = MetricsCollector()
        mc.record_ocr_call(success=False)
        assert mc.metrics.ocr_call_count == 1
        assert mc.metrics.ocr_failure_count == 1
        assert mc.metrics.ocr_success_count == 0

    def test_record_search_query(self):
        mc = MetricsCollector()
        mc.record_search_query(latency_seconds=0.05)
        assert mc.metrics.search_query_count == 1
        assert mc.metrics.total_search_latency == 0.05

    def test_record_cache_hit(self):
        mc = MetricsCollector()
        mc.record_cache_hit()
        assert mc.metrics.cache_hits == 1

    def test_record_cache_miss(self):
        mc = MetricsCollector()
        mc.record_cache_miss()
        assert mc.metrics.cache_misses == 1

    def test_record_indexing_retry(self):
        mc = MetricsCollector()
        mc.record_indexing_retry()
        assert mc.metrics.indexing_retry_count == 1

    def test_reset_clears_all_metrics(self):
        mc = MetricsCollector()
        mc.record_upload()
        mc.record_ocr_call(success=True, processing_time=1.0)
        mc.reset()
        assert mc.metrics.upload_count == 0
        assert mc.metrics.ocr_call_count == 0

    def test_multiple_records_accumulate(self):
        mc = MetricsCollector()
        for _ in range(5):
            mc.record_upload()
        assert mc.metrics.upload_count == 5


class TestHealthChecker:
    def test_empty_checker_is_healthy(self):
        hc = HealthChecker()
        status = hc.check_all()
        assert status.healthy is True
        assert status.checks == []

    def test_passing_check(self):
        hc = HealthChecker()
        hc.register("storage", lambda: True)
        status = hc.check_all()
        assert status.healthy is True
        assert len(status.checks) == 1
        assert status.checks[0].name == "storage"
        assert status.checks[0].healthy is True

    def test_failing_check(self):
        hc = HealthChecker()
        hc.register("storage", lambda: False)
        status = hc.check_all()
        assert status.healthy is False
        assert status.checks[0].healthy is False

    def test_exception_in_check_marks_unhealthy(self):
        hc = HealthChecker()
        hc.register("db", lambda: (_ for _ in ()).throw(ConnectionError("down")))
        status = hc.check_all()
        assert status.healthy is False
        assert "ERROR" in status.checks[0].message

    def test_all_checks_run_even_if_one_fails(self):
        hc = HealthChecker()
        hc.register("a", lambda: False)
        hc.register("b", lambda: True)
        status = hc.check_all()
        assert len(status.checks) == 2
        assert status.healthy is False

    def test_check_single_component(self):
        hc = HealthChecker()
        hc.register("storage", lambda: True)
        result = hc.check("storage")
        assert result is not None
        assert result.healthy is True

    def test_check_unregistered_component_returns_none(self):
        hc = HealthChecker()
        assert hc.check("unknown") is None

    def test_latency_is_recorded(self):
        hc = HealthChecker()
        hc.register("fast", lambda: True)
        status = hc.check_all()
        assert status.checks[0].latency_ms >= 0.0


class TestGlobalSingletons:
    def setup_method(self):
        reset_metrics_collector()
        reset_health_checker()

    def teardown_method(self):
        reset_metrics_collector()
        reset_health_checker()

    def test_get_metrics_collector_singleton(self):
        mc1 = get_metrics_collector()
        mc2 = get_metrics_collector()
        assert mc1 is mc2

    def test_reset_metrics_collector(self):
        mc1 = get_metrics_collector()
        reset_metrics_collector()
        mc2 = get_metrics_collector()
        assert mc1 is not mc2

    def test_get_health_checker_singleton(self):
        hc1 = get_health_checker()
        hc2 = get_health_checker()
        assert hc1 is hc2

    def test_reset_health_checker(self):
        hc1 = get_health_checker()
        reset_health_checker()
        hc2 = get_health_checker()
        assert hc1 is not hc2

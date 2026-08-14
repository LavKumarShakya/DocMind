"""Unit tests for latency aggregation helpers (pure functions)."""

from evaluation.latency import median_ms, p95_ms, percentile, summarize


def test_percentile_nearest_rank():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert percentile(values, 50) == 5.0
    assert percentile(values, 95) == 10.0
    assert percentile(values, 100) == 10.0


def test_percentile_empty_is_zero():
    assert percentile([], 95) == 0.0


def test_summarize_reports_ms_and_count():
    s = summarize([0.5, 1.0, 1.5])
    assert s["mean_ms"] == 1000.0
    assert s["median_ms"] == 1000.0
    assert s["p95_ms"] == 1500.0
    assert s["count"] == 3


def test_summarize_empty():
    s = summarize([])
    assert s["count"] == 0
    assert s["mean_ms"] == 0.0
    assert s["median_ms"] == 0.0
    assert s["p95_ms"] == 0.0


def test_median_and_p95_helpers():
    values = [0.001, 0.002, 0.003]
    assert median_ms(values) == 2.0
    assert p95_ms(values) == 3.0
    assert median_ms([]) == 0.0
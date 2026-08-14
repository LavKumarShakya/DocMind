"""Latency helpers: mean / median / P95 over per-call timings (seconds)."""

from __future__ import annotations

import math
from statistics import mean, median

from evaluation.metrics import mean_of


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile (0..100). Returns 0.0 for an empty list."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = max(1, math.ceil(len(sorted_values) * p / 100.0))
    return sorted_values[rank - 1]


def summarize(values: list[float]) -> dict[str, float]:
    """Aggregate a list of per-call durations into mean/median/p95."""
    return {
        "mean_ms": round(mean_of(values) * 1000.0, 1),
        "median_ms": round(median(values) * 1000.0, 1) if values else 0.0,
        "p95_ms": round(percentile(values, 95) * 1000.0, 1),
        "count": len(values),
    }


def p95_ms(values: list[float]) -> float:
    return round(percentile(values, 95) * 1000.0, 1)


def median_ms(values: list[float]) -> float:
    return round(median(values) * 1000.0, 1) if values else 0.0
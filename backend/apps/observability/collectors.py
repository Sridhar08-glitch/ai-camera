"""
In-memory metric accumulators with bounded cardinality (Phase 2 §14 / ADR-017).

Counters and summaries accumulate in process memory; a Celery task flushes
aggregates to SystemMetric, then resets. Metric names and their allowed label
keys are declared in ALLOWED — unknown names or labels are rejected so cardinality
cannot explode. No per-request database writes happen here.
"""
from __future__ import annotations

import threading

COUNTER = "counter"
SUMMARY = "summary"

# name -> (kind, unit, runtime, allowed label keys)
ALLOWED: dict[str, tuple[str, str, str, frozenset[str]]] = {
    "http_requests_total": (COUNTER, "count", "django", frozenset({"method", "status_class"})),
    "http_errors_total": (COUNTER, "count", "django", frozenset({"status_class"})),
    "http_request_latency_ms": (SUMMARY, "ms", "django", frozenset({"method"})),
    "celery_task_total": (COUNTER, "count", "celery", frozenset({"task", "state"})),
    "celery_task_duration_ms": (SUMMARY, "ms", "celery", frozenset({"task"})),
}

_lock = threading.Lock()
_counters: dict[tuple[str, frozenset], float] = {}
_summaries: dict[tuple[str, frozenset], list] = {}  # [count, sum, min, max]


class MetricError(ValueError):
    pass


def _validated_key(name: str, labels: dict | None) -> tuple[str, frozenset]:
    if name not in ALLOWED:
        raise MetricError(f"unknown metric '{name}'")
    allowed_labels = ALLOWED[name][3]
    labels = labels or {}
    extra = set(labels) - allowed_labels
    if extra:
        raise MetricError(f"labels {sorted(extra)} not allowed for '{name}'")
    # Normalize label values to short strings to bound cardinality further.
    norm = frozenset((k, str(v)[:32]) for k, v in labels.items())
    return name, norm


def incr(name: str, labels: dict | None = None, amount: float = 1.0) -> None:
    if ALLOWED.get(name, (None,))[0] != COUNTER:
        raise MetricError(f"'{name}' is not a counter")
    key = _validated_key(name, labels)
    with _lock:
        _counters[key] = _counters.get(key, 0.0) + amount


def observe(name: str, value: float, labels: dict | None = None) -> None:
    if ALLOWED.get(name, (None,))[0] != SUMMARY:
        raise MetricError(f"'{name}' is not a summary")
    key = _validated_key(name, labels)
    with _lock:
        agg = _summaries.get(key)
        if agg is None:
            _summaries[key] = [1, value, value, value]
        else:
            agg[0] += 1
            agg[1] += value
            agg[2] = min(agg[2], value)
            agg[3] = max(agg[3], value)


def snapshot_and_reset() -> list[dict]:
    """Return aggregated rows and clear accumulators (called by the flush task)."""
    with _lock:
        counters = dict(_counters)
        summaries = dict(_summaries)
        _counters.clear()
        _summaries.clear()

    rows: list[dict] = []
    for (name, labelset), total in counters.items():
        kind, unit, runtime, _ = ALLOWED[name]
        rows.append({"name": name, "runtime": runtime, "unit": unit,
                     "value": total, "labels": dict(labelset)})
    for (name, labelset), (count, total, mn, mx) in summaries.items():
        kind, unit, runtime, _ = ALLOWED[name]
        base = dict(labelset)
        rows.append({"name": name, "runtime": runtime, "unit": unit,
                     "value": total / count if count else 0.0, "labels": {**base, "stat": "avg"}})
        rows.append({"name": name, "runtime": runtime, "unit": unit,
                     "value": mx, "labels": {**base, "stat": "max"}})
        rows.append({"name": name, "runtime": runtime, "unit": "count",
                     "value": count, "labels": {**base, "stat": "count"}})
    return rows

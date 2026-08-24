"""Bounded ingestion metrics (Phase 4 §19). No video-id labels (cardinality)."""
from __future__ import annotations

from apps.observability import collectors

# Register Phase 4 metric definitions (extends the allowlist).
collectors.ALLOWED.update({
    "videos_uploaded_total": (collectors.COUNTER, "count", "django", frozenset()),
    "upload_failures_total": (collectors.COUNTER, "count", "django", frozenset({"reason"})),
    "upload_bytes": (collectors.SUMMARY, "bytes", "django", frozenset()),
})


def record_upload_success(size_bytes: int) -> None:
    collectors.incr("videos_uploaded_total")
    collectors.observe("upload_bytes", float(size_bytes))


def record_upload_failure(reason: str) -> None:
    collectors.incr("upload_failures_total", {"reason": reason[:32]})

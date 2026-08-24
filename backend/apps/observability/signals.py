"""Celery task metric collection via signals (Phase 2 §14)."""
from __future__ import annotations

import time

from celery.signals import task_postrun, task_prerun

from apps.observability.collectors import incr, observe

_starts: dict[str, float] = {}


@task_prerun.connect
def _on_prerun(task_id=None, task=None, **kwargs):
    if task_id:
        _starts[task_id] = time.perf_counter()


@task_postrun.connect
def _on_postrun(task_id=None, task=None, state=None, **kwargs):
    name = getattr(task, "name", "unknown")
    incr("celery_task_total", {"task": name, "state": str(state or "unknown")})
    start = _starts.pop(task_id, None)
    if start is not None:
        observe("celery_task_duration_ms", (time.perf_counter() - start) * 1000, {"task": name})

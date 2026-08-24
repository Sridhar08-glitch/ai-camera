"""Metric flush task (Phase 2 §22). Writes aggregated rows; no per-event writes."""
from __future__ import annotations

import socket

from celery import shared_task
from django.utils import timezone

from apps.observability.collectors import snapshot_and_reset
from apps.observability.models import SystemMetric


@shared_task(name="apps.observability.tasks.flush_system_metrics")
def flush_system_metrics() -> int:
    rows = snapshot_and_reset()
    if not rows:
        return 0
    bucket = timezone.now()
    host = socket.gethostname()[:128]
    objs = [
        SystemMetric(
            name=r["name"],
            runtime=r["runtime"],
            value=r["value"],
            unit=r["unit"],
            labels=r["labels"],
            host=host,
            bucket_start=bucket,
        )
        for r in rows
    ]
    SystemMetric.objects.bulk_create(objs)
    return len(objs)

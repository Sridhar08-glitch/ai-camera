"""Celery application for the platform (Phase 1)."""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("traffic_platform")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic heartbeat so readiness can observe worker liveness WITHOUT dispatching
# a task on every /readyz call (clarification #3). Beat runs this every 30s; the
# task writes a TTL key to Redis that readyz inspects.
app.conf.beat_schedule = {
    "worker-heartbeat": {
        "task": "apps.common.tasks.write_worker_heartbeat",
        "schedule": crontab(minute="*"),  # every minute; TTL is 60s
    }
}
# Also run once shortly after worker start via a signal-free periodic tick at 30s.
app.conf.beat_schedule["worker-heartbeat-30s"] = {
    "task": "apps.common.tasks.write_worker_heartbeat",
    "schedule": 30.0,
}

# Phase 2 — flush aggregated in-memory metrics to SystemMetric periodically.
app.conf.beat_schedule["flush-system-metrics"] = {
    "task": "apps.observability.tasks.flush_system_metrics",
    "schedule": 60.0,
}

# Phase 2 — evaluate retention policies daily (each policy honors its dry_run_default).
app.conf.beat_schedule["evaluate-retention"] = {
    "task": "apps.retention.tasks.evaluate_retention",
    "schedule": crontab(hour="3", minute="30"),
}

# Phase 4 — reconcile video storage (stale temp uploads + missing-file flagging).
app.conf.beat_schedule["reconcile-storage"] = {
    "task": "apps.ingestion.tasks.reconcile_storage",
    "schedule": crontab(minute="15"),
}

# Phase 5 — stale processing-session watchdog (heartbeat-loss recovery). This is the
# ONLY processing work in Celery; no CV/decoding runs in a Celery worker (ADR-002).
app.conf.beat_schedule["reconcile-stale-sessions"] = {
    "task": "apps.processing.tasks.reconcile_stale_sessions",
    "schedule": 60.0,
}


@app.task(name="config.debug_task")
def debug_task() -> str:
    return "ok"

"""
Common Celery tasks (Phase 1).

- `ping`: trivial round-trip proof used by tests.
- `write_worker_heartbeat`: periodic task (Celery beat) that writes a TTL key
  to Redis so /readyz can observe worker liveness WITHOUT dispatching a task on
  every readiness request (clarification #3).
"""
from __future__ import annotations

import time

from celery import shared_task
from django.conf import settings

from apps.common.redis_client import get_redis


@shared_task(name="apps.common.tasks.ping")
def ping() -> dict:
    return {"pong": True, "ts": time.time()}


@shared_task(name="apps.common.tasks.write_worker_heartbeat")
def write_worker_heartbeat() -> str:
    key = settings.CELERY_HEARTBEAT_KEY
    ttl = settings.CELERY_HEARTBEAT_TTL_SECONDS
    get_redis().set(key, str(time.time()), ex=ttl)
    return key

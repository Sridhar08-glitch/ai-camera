"""Celery task tests (eager mode) — proves the task path and heartbeat."""
from __future__ import annotations

import time

import pytest
from django.conf import settings

from apps.common.redis_client import get_redis
from apps.common.tasks import ping, write_worker_heartbeat

pytestmark = pytest.mark.django_db


def test_ping_task_round_trip():
    result = ping.delay().get(timeout=5)
    assert result["pong"] is True
    assert "ts" in result


def test_write_worker_heartbeat_sets_ttl_key():
    get_redis().delete(settings.CELERY_HEARTBEAT_KEY)
    key = write_worker_heartbeat.delay().get(timeout=5)
    assert key == settings.CELERY_HEARTBEAT_KEY
    raw = get_redis().get(settings.CELERY_HEARTBEAT_KEY)
    assert raw is not None
    assert (time.time() - float(raw)) < 5

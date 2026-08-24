"""Health + readiness tests, including dependency-failure paths (clarification #8)."""
from __future__ import annotations

import time

import pytest

from apps.common.redis_client import get_redis
from django.conf import settings

pytestmark = pytest.mark.django_db


def test_healthz_ok(api):
    resp = api.get("/api/healthz")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "ok"


def test_readyz_reports_all_components(api):
    resp = api.get("/api/readyz")
    body = resp.json()["data"] if "data" in resp.json() else resp.json()
    assert set(body["checks"]) == {"database", "redis", "celery"}


def test_readyz_ready_when_heartbeat_fresh(api):
    # Simulate a live worker by writing a fresh heartbeat (as the beat task would).
    get_redis().set(settings.CELERY_HEARTBEAT_KEY, str(time.time()),
                    ex=settings.CELERY_HEARTBEAT_TTL_SECONDS)
    resp = api.get("/api/readyz")
    assert resp.status_code == 200
    assert resp.json()["data"]["checks"]["celery"]["ok"] is True


def test_readyz_503_when_worker_heartbeat_missing(api):
    get_redis().delete(settings.CELERY_HEARTBEAT_KEY)
    resp = api.get("/api/readyz")
    assert resp.status_code == 503
    assert resp.json()["data"]["checks"]["celery"]["ok"] is False


def test_readyz_503_when_redis_down(api, monkeypatch):
    class BrokenRedis:
        def ping(self):
            raise ConnectionError("redis down")

        def get(self, *a, **k):
            raise ConnectionError("redis down")

    monkeypatch.setattr("apps.health.views.get_redis", lambda: BrokenRedis())
    resp = api.get("/api/readyz")
    assert resp.status_code == 503
    assert resp.json()["data"]["checks"]["redis"]["ok"] is False


def test_readyz_503_when_database_down(api, monkeypatch):
    def boom(self):
        return {"ok": False, "error": "db down"}

    monkeypatch.setattr("apps.health.views.ReadyzView._check_database", boom)
    resp = api.get("/api/readyz")
    assert resp.status_code == 503
    assert resp.json()["data"]["checks"]["database"]["ok"] is False

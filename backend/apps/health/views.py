"""
Liveness and readiness endpoints (Phase 1 §13).

- /api/healthz : liveness — process is up. Always 200 if Django serves.
- /api/readyz  : readiness — checks PostgreSQL, Redis, and Celery worker
  liveness. Celery is checked via a cached heartbeat key (written by a beat
  task) rather than dispatching a task per request (clarification #3).

No fake success: any failed dependency yields 503 with the failing component
named (clarification #8).
"""
from __future__ import annotations

import time

from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.redis_client import get_redis
from django.conf import settings


class HealthzView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        return Response({"status": "ok"})


class ReadyzView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        checks = {
            "database": self._check_database(),
            "redis": self._check_redis(),
            "celery": self._check_celery(),
        }
        healthy = all(c["ok"] for c in checks.values())
        code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            {"status": "ready" if healthy else "not_ready", "checks": checks},
            status=code,
        )

    def _check_database(self) -> dict:
        try:
            with connections["default"].cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return {"ok": True}
        except OperationalError as exc:
            return {"ok": False, "error": str(exc)[:200]}
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": str(exc)[:200]}

    def _check_redis(self) -> dict:
        try:
            get_redis().ping()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}

    def _check_celery(self) -> dict:
        """Inspect the worker heartbeat key (no task dispatch)."""
        try:
            raw = get_redis().get(settings.CELERY_HEARTBEAT_KEY)
            if raw is None:
                return {"ok": False, "error": "no worker heartbeat"}
            age = time.time() - float(raw)
            ok = age <= settings.CELERY_HEARTBEAT_TTL_SECONDS
            return {"ok": ok, "heartbeat_age_seconds": round(age, 1)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}

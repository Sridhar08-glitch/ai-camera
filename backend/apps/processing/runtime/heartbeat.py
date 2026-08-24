"""
Heartbeat helpers (Phase 5 §23). Redis TTL keys are the fast liveness signal;
the ProcessingSession.last_heartbeat_at column is the durable mirror the watchdog
reads. Redis is best-effort — Postgres remains authoritative for session truth.
"""
from __future__ import annotations

import time

from django.conf import settings

from apps.common.redis_client import get_redis


def session_key(session_id) -> str:
    return f"{settings.CV_HEARTBEAT_KEY_PREFIX}:{session_id}:heartbeat"


def write_session_heartbeat(session_id, *, redis_client=None) -> None:
    r = redis_client or get_redis()
    try:
        r.set(session_key(session_id), str(time.time()), ex=settings.CV_HEARTBEAT_TTL_SECONDS)
    except Exception:  # Redis down is non-fatal; DB mirror still updates
        pass


def read_session_heartbeat_age(session_id, *, redis_client=None) -> float | None:
    r = redis_client or get_redis()
    try:
        raw = r.get(session_key(session_id))
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return time.time() - float(raw)
    except (TypeError, ValueError):
        return None


def clear_session_heartbeat(session_id, *, redis_client=None) -> None:
    r = redis_client or get_redis()
    try:
        r.delete(session_key(session_id))
    except Exception:
        pass


def write_runtime_heartbeat(runtime_id: str, *, redis_client=None) -> None:
    r = redis_client or get_redis()
    try:
        r.set(settings.CV_RUNTIME_HEARTBEAT_KEY, str(time.time()),
              ex=settings.CV_HEARTBEAT_TTL_SECONDS)
    except Exception:
        pass


def read_runtime_heartbeat_age(*, redis_client=None) -> float | None:
    r = redis_client or get_redis()
    try:
        raw = r.get(settings.CV_RUNTIME_HEARTBEAT_KEY)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return time.time() - float(raw)
    except (TypeError, ValueError):
        return None

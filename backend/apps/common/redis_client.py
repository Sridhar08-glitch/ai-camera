"""Shared Redis client helper (health checks, heartbeat)."""
from __future__ import annotations

import redis
from django.conf import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return a lazily-created shared Redis client for REDIS_URL."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
    return _client

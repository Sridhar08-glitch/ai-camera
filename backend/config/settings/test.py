"""
Test settings.

Uses the real PostgreSQL and Redis infrastructure (Phase 0 rule: no fake
fallbacks). Django creates an isolated test database. The channel layer uses
the in-memory backend so WebSocket consumer tests do not require a live Redis
for the transport, while integration tests still exercise real Redis/Celery
explicitly where marked.
"""
from .base import *  # noqa: F401,F403
from .base import DATABASES, LOG_LEVEL
from config.logging import configure_logging

# Close DB connections eagerly in tests so that connections opened on async
# thread-sensitive executors (WebSocket consumer + middleware user lookup) are
# released by close_old_connections() and do not block test-database teardown.
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Send request bodies as JSON by default so nested dict payloads (config,
# input_spec, class_map, metadata) are supported in API tests.
REST_FRAMEWORK["TEST_REQUEST_DEFAULT_FORMAT"] = "json"  # noqa: F405

# Human-readable (non-JSON) logs during tests, warnings and above only.
configure_logging(json_logs=False, level="WARNING")

DEBUG = False

# Faster password hashing for tests.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# In-memory channel layer for deterministic consumer unit tests.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Run Celery tasks eagerly in-process for task-logic tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

_ = LOG_LEVEL  # referenced to keep import explicit

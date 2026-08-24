"""
Base Django settings for the AI Traffic Intelligence Platform (Phase 1).

Environment-driven via django-environ. Split into base/dev/test.
Phase 0 rule: no secrets hardcoded; all config via environment.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ

# backend/ directory (two levels up from this file: config/settings/base.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# Read .env if present (dev). In CI/test, environment variables may be set directly.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-override-in-env")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.health",
    "apps.realtime",
    # Phase 2 — platform foundations
    "apps.audit",
    "apps.governance",
    "apps.retention",
    "apps.observability",
    # Phase 3 — traffic network configuration
    "apps.network",
    # Phase 4 — video ingestion
    "apps.ingestion",
    # Phase 5 — processing session engine + CV runtime
    "apps.processing",
    # Phase 6T-A — training-data governance (no torch; training itself is isolated)
    "apps.datasets",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "apps.common.middleware.RequestIDMiddleware",
    "apps.observability.middleware.MetricsMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.common.middleware.RequestLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — single PostgreSQL instance, logical domain separation.
# Phase 1 schema strategy (ADR-013): all Phase 1 tables live in `public`.
# The config/operational/analytical/ai schemas are created by init_db for
# future domain tables but Phase 1 does NOT route framework/auth tables into
# custom schemas (migration safety > premature separation).
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# DRF + SimpleJWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "apps.common.responses.EnvelopeJSONRenderer",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "config.exceptions.standard_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Refresh-token cookie (HttpOnly) — clarification #1.
REFRESH_COOKIE = {
    "NAME": env("REFRESH_COOKIE_NAME", default="refresh_token"),
    "SECURE": env.bool("REFRESH_COOKIE_SECURE", default=False),
    "SAMESITE": env("REFRESH_COOKIE_SAMESITE", default="Lax"),
    "DOMAIN": env("REFRESH_COOKIE_DOMAIN", default="") or None,
    "PATH": "/api/v1/auth",
    "HTTPONLY": True,
}

# ---------------------------------------------------------------------------
# Channels — Redis channel layer
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("REDIS_URL", default="redis://127.0.0.1:6379/0")]},
    }
}

WS_HEARTBEAT_SECONDS = env.int("WS_HEARTBEAT_SECONDS", default=20)

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Health heartbeat written by the worker via a beat task; readyz reads it (clarification #3).
CELERY_HEARTBEAT_KEY = "celery:worker:heartbeat"
CELERY_HEARTBEAT_TTL_SECONDS = env.int("CELERY_HEARTBEAT_TTL_SECONDS", default=60)

# ---------------------------------------------------------------------------
# Caching / Redis client (shared helper reads this)
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# I18N / static
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging (structured) — configured in config.logging
# ---------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_JSON = env.bool("LOG_JSON", default=True)

# ---------------------------------------------------------------------------
# Phase 2 — governance / retention / metrics
# ---------------------------------------------------------------------------
# Artifact registry root (validated; prevents path traversal in artifact refs).
ARTIFACT_ROOT = env("ARTIFACT_ROOT", default=str(BASE_DIR / "artifacts"))

# Retention engine controls.
RETENTION_ENABLED = env.bool("RETENTION_ENABLED", default=True)
RETENTION_MAX_DELETES_PER_RUN = env.int("RETENTION_MAX_DELETES_PER_RUN", default=100000)

# Metric sampling interval (seconds) for the flush task.
METRIC_SAMPLE_INTERVAL_SECONDS = env.int("METRIC_SAMPLE_INTERVAL_SECONDS", default=60)

# Phase 3 — cap on free-form network metadata JSON size (bytes) to guard against
# oversized payloads.
NETWORK_METADATA_MAX_BYTES = env.int("NETWORK_METADATA_MAX_BYTES", default=8192)

# ---------------------------------------------------------------------------
# Phase 4 — video ingestion & storage
# ---------------------------------------------------------------------------
VIDEO_STORAGE_ROOT = env("VIDEO_STORAGE_ROOT", default=str(BASE_DIR / "media" / "videos"))
VIDEO_TEMP_ROOT = env("VIDEO_TEMP_ROOT", default=str(BASE_DIR / "media" / "tmp"))
VIDEO_TEMP_MAX_AGE_SECONDS = env.int("VIDEO_TEMP_MAX_AGE_SECONDS", default=3600)
# Upload/capacity limits.
MAX_UPLOAD_BYTES = env.int("MAX_UPLOAD_BYTES", default=2 * 1024 * 1024 * 1024)  # 2 GiB
VIDEO_STORAGE_QUOTA_BYTES = env.int("VIDEO_STORAGE_QUOTA_BYTES", default=20 * 1024 * 1024 * 1024)  # 20 GiB
MIN_FREE_DISK_BYTES = env.int("MIN_FREE_DISK_BYTES", default=2 * 1024 * 1024 * 1024)  # 2 GiB reserve
# Thumbnails.
VIDEO_THUMBNAIL_ENABLED = env.bool("VIDEO_THUMBNAIL_ENABLED", default=True)
VIDEO_THUMBNAIL_MAX_DIM = env.int("VIDEO_THUMBNAIL_MAX_DIM", default=640)
# Stream large multipart uploads straight to disk (no in-memory buffering).
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=5 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = env.int("FILE_UPLOAD_MAX_MEMORY_SIZE", default=5 * 1024 * 1024)

# ---------------------------------------------------------------------------
# Phase 5 — processing session engine + CV runtime (ADR-024/025/027)
# ---------------------------------------------------------------------------
# Concurrency: default one active heavy session on 8 GB VRAM (frozen §14).
CV_MAX_CONCURRENT_SESSIONS = env.int("CV_MAX_CONCURRENT_SESSIONS", default=1)
# Identity/version of the runtime process (surfaced on the session + heartbeat).
CV_RUNTIME_VERSION = env("CV_RUNTIME_VERSION", default="phase5")
# Heartbeat + watchdog (Redis TTL key + durable DB mirror).
CV_HEARTBEAT_TTL_SECONDS = env.int("CV_HEARTBEAT_TTL_SECONDS", default=30)
CV_HEARTBEAT_KEY_PREFIX = env("CV_HEARTBEAT_KEY_PREFIX", default="cv:session")
CV_RUNTIME_HEARTBEAT_KEY = env("CV_RUNTIME_HEARTBEAT_KEY", default="cv:runtime:heartbeat")
# Stale threshold beyond which the watchdog FAILs a runtime-active session.
CV_STALE_SESSION_SECONDS = env.int("CV_STALE_SESSION_SECONDS", default=90)
# Bounded progress persistence (never per-frame): whichever comes first.
CV_PROGRESS_INTERVAL_SECONDS = env.float("CV_PROGRESS_INTERVAL_SECONDS", default=2.0)
CV_PROGRESS_EVERY_N_FRAMES = env.int("CV_PROGRESS_EVERY_N_FRAMES", default=100)
# Runtime poll cadence when idle (claim loop) + command check.
CV_RUNTIME_POLL_SECONDS = env.float("CV_RUNTIME_POLL_SECONDS", default=1.0)
# Per-frame debug logging is OFF by default (bounded log volume, §29).
CV_LOG_FRAMES = env.bool("CV_LOG_FRAMES", default=False)
# Prevent creating a second non-terminal session for the same video (§30).
CV_BLOCK_DUPLICATE_ACTIVE = env.bool("CV_BLOCK_DUPLICATE_ACTIVE", default=True)

# ---------------------------------------------------------------------------
# Detector runtime (Phase 6). Infrastructure only — no third-party weights.
# Device policy: REQUIRE_GPU | PREFER_GPU | CPU_ONLY. PREFER_GPU falls back to CPU
# truthfully (actual ONNX execution provider is always reported, never faked).
CV_DETECTOR_DEVICE_POLICY = env("CV_DETECTOR_DEVICE_POLICY", default="PREFER_GPU")
# Letterbox target square size fed to the model (default 640).
CV_DETECTOR_INPUT_SIZE = env.int("CV_DETECTOR_INPUT_SIZE", default=640)
# PROVISIONAL default thresholds (not accuracy-tuned; no mAP claims — §guardrails).
CV_DETECTOR_CONF_THRESHOLD = env.float("CV_DETECTOR_CONF_THRESHOLD", default=0.25)
CV_DETECTOR_IOU_THRESHOLD = env.float("CV_DETECTOR_IOU_THRESHOLD", default=0.45)
# Max detections retained per frame after NMS (bounded JSON payload).
CV_DETECTOR_MAX_DETECTIONS = env.int("CV_DETECTOR_MAX_DETECTIONS", default=300)
# Persist detections in bulk every N processed frames (never per-frame DB write).
CV_DETECTOR_PERSIST_EVERY_N = env.int("CV_DETECTOR_PERSIST_EVERY_N", default=50)
# Estimated VRAM budget (MB) a detector session reserves (interface; PROVISIONAL).
CV_DETECTOR_EST_VRAM_MB = env.int("CV_DETECTOR_EST_VRAM_MB", default=1500)

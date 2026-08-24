"""Development settings — native Windows local execution."""
from .base import *  # noqa: F401,F403
from .base import LOG_JSON, LOG_LEVEL
from config.logging import configure_logging

# Configure structlog for development.
configure_logging(json_logs=LOG_JSON, level=LOG_LEVEL)

# Dev conveniences (still honoring env-driven DEBUG in base).
INTERNAL_IPS = ["127.0.0.1"]

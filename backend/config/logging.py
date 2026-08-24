"""
Structured logging foundation using structlog (Phase 1 §18).

Emits JSON logs (toggleable to console renderer in dev). A request-id is bound
via contextvars by RequestIDMiddleware so every log line during a request is
correlated. Celery task logs include task metadata.
"""
from __future__ import annotations

import logging
import sys

import structlog

# Shared processor chain used for both structlog and stdlib log records.
_TIMESTAMPER = structlog.processors.TimeStamper(fmt="iso", utc=True)

_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    _TIMESTAMPER,
    structlog.processors.StackInfoRenderer(),
]


def configure_logging(*, json_logs: bool = True, level: str = "INFO") -> None:
    """Configure structlog + stdlib logging. Idempotent."""
    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Tame noisy loggers.
    for noisy in ("daphne", "asyncio"):
        logging.getLogger(noisy).setLevel("WARNING")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

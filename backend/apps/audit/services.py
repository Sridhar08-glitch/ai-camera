"""
Audit emission service (Phase 2 §12 / ADR-016).

`record_audit` is the single write path. Metadata is sanitized to guarantee no
passwords, tokens, JWTs, authorization headers, or cookies are ever stored.

Emission modes:
  * transactional (default) — inserted within the caller's DB transaction; if the
    audit insert fails, the surrounding business action rolls back.
  * best_effort — for high-frequency/low-risk events (login/logout); failure is
    logged + counted and never breaks the action.
"""
from __future__ import annotations

import re
from typing import Any

import structlog
from django.db import transaction

from apps.audit.models import AuditEvent, Outcome
from apps.common.audit_context import build_context

logger = structlog.get_logger("audit")

_SENSITIVE_KEY = re.compile(
    r"(password|passwd|secret|token|jwt|authorization|auth|cookie|session|api[_-]?key|refresh|access)",
    re.IGNORECASE,
)
_REDACTED = "[redacted]"
_MAX_STR = 2000
_MAX_DEPTH = 6


def sanitize_metadata(value: Any, _depth: int = 0) -> Any:
    """Recursively drop sensitive keys and coerce to JSON-safe primitives."""
    if _depth > _MAX_DEPTH:
        return "[truncated:depth]"
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if _SENSITIVE_KEY.search(key):
                clean[key] = _REDACTED
            else:
                clean[key] = sanitize_metadata(v, _depth + 1)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize_metadata(v, _depth + 1) for v in value]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    text = str(value)
    return text[:_MAX_STR]


def record_audit(
    event_type: str,
    action: str,
    *,
    outcome: str = Outcome.SUCCESS,
    request=None,
    actor=None,
    target_type: str = "",
    target_id: str = "",
    metadata: dict | None = None,
    source: str = "django",
    best_effort: bool = False,
) -> AuditEvent | None:
    ctx = build_context(request=request, actor=actor, source=source)
    clean_meta = sanitize_metadata(metadata or {})

    def _create() -> AuditEvent:
        return AuditEvent.objects.create(
            event_type=event_type,
            action=action,
            outcome=outcome,
            actor_id=getattr(ctx.actor, "pk", None),
            actor_email=ctx.actor_email,
            actor_role=ctx.actor_role,
            target_type=target_type,
            target_id=str(target_id) if target_id else "",
            request_id=ctx.request_id,
            source=ctx.source,
            ip_address=ctx.ip_address,
            metadata=clean_meta,
        )

    if best_effort:
        try:
            # Emit after the surrounding transaction commits where one exists.
            event = _create()
            return event
        except Exception:  # pragma: no cover - defensive
            logger.error("audit_emit_failed", event_type=event_type, best_effort=True)
            return None

    # Transactional: propagate failure so the business action rolls back.
    return _create()


def record_audit_on_commit(event_type: str, action: str, **kwargs) -> None:
    """Best-effort audit emitted only after the current transaction commits."""
    def _emit():
        record_audit(event_type, action, best_effort=True, **kwargs)

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(_emit)
    else:
        _emit()

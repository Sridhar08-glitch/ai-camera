"""
Authoritative state-transition service (Phase 5 / ADR-024).

The ONLY code path that writes ProcessingSession.state. Validates against the
frozen transition table, stamps the entry timestamp, writes an AuditEvent, emits
a structured log, and updates metrics on terminal transitions. Invalid
transitions are rejected (InvalidTransition) and logged as observability events.
"""
from __future__ import annotations

import structlog
from django.db import transaction
from django.utils import timezone

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.processing import observability
from apps.processing.states import (
    STATE_TIMESTAMP_FIELD,
    ProcessingState,
    can_transition,
    is_terminal,
)

logger = structlog.get_logger("processing")

# state -> audit EventType for that entry (subset; others are not separately audited)
_AUDIT_EVENT = {
    ProcessingState.QUEUED: EventType.PROCESSING_QUEUED,
    ProcessingState.INITIALIZING: EventType.PROCESSING_STARTED,
    ProcessingState.PAUSED: EventType.PROCESSING_PAUSED,
    ProcessingState.RUNNING: None,  # resume audited explicitly via services.commands
    ProcessingState.COMPLETED: EventType.PROCESSING_COMPLETED,
    ProcessingState.FAILED: EventType.PROCESSING_FAILED,
    ProcessingState.CANCELLED: EventType.PROCESSING_CANCELLED,
    ProcessingState.STOPPED: EventType.PROCESSING_STOPPED,
}

_FINISH_OUTCOME = {
    ProcessingState.COMPLETED: "completed",
    ProcessingState.FAILED: "failed",
    ProcessingState.CANCELLED: "cancelled",
    ProcessingState.STOPPED: "stopped",
}


class InvalidTransition(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"invalid transition {from_state} -> {to_state}")


def transition(
    session,
    to_state: str,
    *,
    actor=None,
    request=None,
    source: str = "cv_runtime",
    reason: str = "",
    error_code: str = "",
    error_message: str = "",
    extra_fields: dict | None = None,
) -> "object":
    """Atomically move `session` to `to_state`. Returns the refreshed session.

    Re-reads the row under SELECT FOR UPDATE so concurrent writers cannot race on
    `state`. Raises InvalidTransition for a forbidden move (no state change).
    """
    from apps.processing.models import ProcessingSession

    with transaction.atomic():
        locked = ProcessingSession.objects.select_for_update().get(pk=session.pk)
        from_state = locked.state

        if from_state == to_state:
            # Idempotent no-op (e.g., re-issued STOP on already STOPPED).
            return locked

        if not can_transition(from_state, to_state):
            logger.warning(
                "processing_invalid_transition",
                session_id=str(locked.id), from_state=from_state, to_state=to_state,
            )
            raise InvalidTransition(from_state, to_state)

        locked.state = to_state
        now = timezone.now()
        ts_field = STATE_TIMESTAMP_FIELD.get(to_state)
        if ts_field and getattr(locked, ts_field) is None:
            setattr(locked, ts_field, now)
        if error_code:
            locked.error_code = error_code[:48]
        if error_message:
            locked.error_message = error_message[:500]
        if extra_fields:
            for k, v in extra_fields.items():
                setattr(locked, k, v)

        update_fields = ["state", "updated_at"]
        if ts_field:
            update_fields.append(ts_field)
        if error_code:
            update_fields.append("error_code")
        if error_message:
            update_fields.append("error_message")
        if extra_fields:
            update_fields.extend(extra_fields.keys())
        locked.save(update_fields=list(dict.fromkeys(update_fields)))

        event_type = _AUDIT_EVENT.get(to_state)
        if event_type is not None:
            record_audit(
                event_type, f"processing.{to_state}",
                request=request, actor=actor, source=source,
                target_type="ProcessingSession", target_id=str(locked.id),
                metadata={
                    "video_id": str(locked.video_asset_id),
                    "snapshot_hash": locked.config_snapshot.snapshot_hash,
                    "from_state": from_state, "to_state": to_state,
                    "error_code": locked.error_code, "reason": reason,
                    "frames_processed": locked.frames_processed,
                },
            )

        logger.info(
            "processing_transition",
            session_id=str(locked.id), runtime_id=locked.runtime_id or None,
            from_state=from_state, to_state=to_state,
            error_code=locked.error_code or None, reason=reason or None,
        )

        if is_terminal(to_state):
            observability.record_finished(_FINISH_OUTCOME.get(to_state, to_state))
            if locked.started_at is not None:
                observability.observe_duration_ms((now - locked.started_at).total_seconds() * 1000.0)

    return locked

"""
Session command service (Phase 5 §21). Django expresses INTENT via
`requested_action`; the CV runtime performs the actual state transition at a safe
frame boundary. The one exception is pre-pickup CANCEL of a CREATED/QUEUED session,
which Django transitions directly (guarded by SELECT FOR UPDATE against a claim race).

Postgres is authoritative; a best-effort Redis publish is the fast path.
"""
from __future__ import annotations

import structlog
from django.db import transaction
from django.utils import timezone

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.common.redis_client import get_redis
from apps.processing.models import ProcessingSession
from apps.processing.services.session import SessionError
from apps.processing.services.state import transition
from apps.processing.states import ProcessingState, RequestedAction

logger = structlog.get_logger("processing")

_PRE_PICKUP = {ProcessingState.CREATED, ProcessingState.QUEUED}


def _publish(session_id, action: str) -> None:
    try:
        get_redis().publish(f"cv:session:{session_id}:commands", action)
    except Exception:  # best-effort; DB is authoritative
        pass


def _set_action(session_id, action: str, *, extra: dict | None = None) -> None:
    fields = {"requested_action": action}
    if extra:
        fields.update(extra)
    ProcessingSession.objects.filter(pk=session_id).update(**fields)


def request_cancel(session: ProcessingSession, *, request=None, actor=None) -> ProcessingSession:
    with transaction.atomic():
        locked = ProcessingSession.objects.select_for_update().get(pk=session.pk)
        if locked.is_terminal:
            return locked  # idempotent
        locked.requested_action = RequestedAction.CANCEL
        locked.cancel_requested_at = locked.cancel_requested_at or timezone.now()
        locked.save(update_fields=["requested_action", "cancel_requested_at", "updated_at"])
        record_audit(
            EventType.PROCESSING_CANCEL_REQUESTED, "processing.cancel_requested",
            request=request, actor=actor, source="django",
            target_type="ProcessingSession", target_id=str(locked.id),
            metadata={"video_id": str(locked.video_asset_id), "state": locked.state},
        )
        pre_pickup = locked.state in _PRE_PICKUP
    if pre_pickup:
        # Runtime hasn't claimed it — Django performs the terminal transition.
        transition(session, ProcessingState.CANCELLED, request=request, actor=actor,
                   source="django", reason="cancel_pre_pickup")
    else:
        _publish(session.pk, RequestedAction.CANCEL)
    session.refresh_from_db()
    return session


def request_stop(session: ProcessingSession, *, request=None, actor=None) -> ProcessingSession:
    locked = ProcessingSession.objects.get(pk=session.pk)
    if locked.is_terminal:
        return locked  # idempotent
    if locked.state in _PRE_PICKUP:
        raise SessionError("not_running", "session has not started; cancel instead", status=409)
    _set_action(session.pk, RequestedAction.STOP)
    _publish(session.pk, RequestedAction.STOP)
    session.refresh_from_db()
    return session


def request_pause(session: ProcessingSession, *, request=None, actor=None) -> ProcessingSession:
    locked = ProcessingSession.objects.get(pk=session.pk)
    if locked.state != ProcessingState.RUNNING:
        raise SessionError("not_running", "can only pause a RUNNING session", status=409)
    _set_action(session.pk, RequestedAction.PAUSE)
    _publish(session.pk, RequestedAction.PAUSE)
    session.refresh_from_db()
    return session


def request_resume(session: ProcessingSession, *, request=None, actor=None) -> ProcessingSession:
    locked = ProcessingSession.objects.get(pk=session.pk)
    if locked.state != ProcessingState.PAUSED:
        raise SessionError("not_paused", "can only resume a PAUSED session", status=409)
    _set_action(session.pk, RequestedAction.RESUME)
    _publish(session.pk, RequestedAction.RESUME)
    session.refresh_from_db()
    return session

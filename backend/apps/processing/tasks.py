"""
Celery tasks for processing (Phase 5 §23). The ONLY processing work in Celery is
the stale-session watchdog — no CV/decoding runs here (frozen ADR-002).
"""
from __future__ import annotations

import structlog
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = structlog.get_logger("processing")


@shared_task(name="apps.processing.tasks.reconcile_stale_sessions")
def reconcile_stale_sessions() -> int:
    """Fail runtime-active sessions whose heartbeat has expired (crash/kill).

    Conservative: stale → FAILED(heartbeat_lost) (manual retry). Never auto-reruns.
    Uses BOTH the Redis heartbeat and the durable DB mirror; a session is stale
    only when it has no fresh liveness from either.
    """
    from datetime import timedelta

    from apps.processing.models import ProcessingSession
    from apps.processing.runtime.heartbeat import read_session_heartbeat_age
    from apps.processing.services.state import InvalidTransition, transition
    from apps.processing.states import RUNTIME_ACTIVE_STATES, ProcessingState

    threshold = settings.CV_STALE_SESSION_SECONDS
    cutoff = timezone.now() - timedelta(seconds=threshold)
    failed = 0

    candidates = ProcessingSession.objects.filter(
        state__in=RUNTIME_ACTIVE_STATES
    ).only("id", "state", "last_heartbeat_at")

    for session in candidates:
        redis_age = read_session_heartbeat_age(session.id)
        if redis_age is not None and redis_age <= threshold:
            continue  # fresh Redis heartbeat
        db_hb = session.last_heartbeat_at
        if db_hb is not None and db_hb > cutoff:
            continue  # fresh DB mirror
        try:
            transition(session, ProcessingState.FAILED, source="celery",
                       error_code="heartbeat_lost",
                       error_message="runtime heartbeat expired (stale session recovery)",
                       reason="watchdog")
            failed += 1
            logger.warning("processing_stale_failed", session_id=str(session.id))
        except InvalidTransition:
            pass  # became terminal concurrently
    return failed

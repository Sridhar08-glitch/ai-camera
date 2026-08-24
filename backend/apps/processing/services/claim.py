"""
Session claim protocol (Phase 5 §10/§25). Atomic QUEUED→INITIALIZING pickup by the
CV runtime. FOR UPDATE SKIP LOCKED guarantees a session is claimed by exactly one
runtime; the concurrency cap bounds active sessions (default 1 on 8 GB VRAM).
"""
from __future__ import annotations

from django.conf import settings
from django.db import transaction

from apps.processing.models import ProcessingSession
from apps.processing.services.state import transition
from apps.processing.states import RUNTIME_ACTIVE_STATES, ProcessingState


def claim_next(runtime_id: str, *, capacity: int | None = None):
    """Claim the oldest QUEUED session if under the concurrency cap. Returns the
    claimed session (state INITIALIZING) or None."""
    cap = settings.CV_MAX_CONCURRENT_SESSIONS if capacity is None else capacity
    with transaction.atomic():
        active = ProcessingSession.objects.filter(state__in=RUNTIME_ACTIVE_STATES).count()
        if active >= cap:
            return None
        session = (ProcessingSession.objects
                   .select_for_update(skip_locked=True)
                   .filter(state=ProcessingState.QUEUED)
                   .order_by("queued_at", "created_at")
                   .first())
        if session is None:
            return None
        session.runtime_id = runtime_id
        session.runtime_version = settings.CV_RUNTIME_VERSION
        session.save(update_fields=["runtime_id", "runtime_version", "updated_at"])
        transition(session, ProcessingState.INITIALIZING, source="cv_runtime",
                   reason="claimed")
    session.refresh_from_db()
    return session

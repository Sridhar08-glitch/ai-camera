"""
Session creation + retry (Phase 5 §5/§8/§24/§30).

Snapshot is captured synchronously at creation (D2). Django then moves the session
CREATED→QUEUED (the only state Django writes besides pre-pickup CANCELLED). A
duplicate non-terminal session per video is rejected (also enforced by a partial
unique index as a hard backstop).
"""
from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, transaction

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.ingestion.models import ValidationStatus, VideoAsset
from apps.processing import observability
from apps.processing.models import ProcessingSession
from apps.processing.services.params import normalize_params
from apps.processing.services.snapshot import capture_snapshot
from apps.processing.services.state import transition
from apps.processing.states import NON_TERMINAL_STATES, ProcessingState


class SessionError(Exception):
    def __init__(self, code: str, message: str = "", *, status: int = 400):
        self.code = code
        self.status = status
        super().__init__(message or code)


def _validate_video(video: VideoAsset) -> None:
    if not video.is_active:
        raise SessionError("video_inactive", "video is archived/inactive", status=409)
    if video.validation_status != ValidationStatus.VALID:
        raise SessionError("video_not_valid", "video is not validated", status=409)


def create_session(*, video_id, params: dict | None, request=None, actor=None) -> ProcessingSession:
    try:
        video = VideoAsset.objects.select_related("camera").get(pk=video_id, is_active=True)
    except VideoAsset.DoesNotExist:
        raise SessionError("video_not_found", "video not found", status=404)

    _validate_video(video)
    norm_params = normalize_params(params)

    if settings.CV_BLOCK_DUPLICATE_ACTIVE:
        if ProcessingSession.objects.filter(
            video_asset=video, state__in=NON_TERMINAL_STATES
        ).exists():
            raise SessionError("duplicate_active_session",
                               "an active processing session already exists for this video",
                               status=409)

    try:
        with transaction.atomic():
            snapshot = capture_snapshot(video)
            session = ProcessingSession.objects.create(
                video_asset=video,
                camera=video.camera,
                requested_by=actor,
                config_snapshot=snapshot,
                processing_params=norm_params,
                state=ProcessingState.CREATED,
            )
            record_audit(
                EventType.PROCESSING_REQUESTED, "processing.requested",
                request=request, actor=actor, source="django",
                target_type="ProcessingSession", target_id=str(session.id),
                metadata={"video_id": str(video.id), "snapshot_hash": snapshot.snapshot_hash,
                          "params": norm_params},
            )
            # CREATED -> QUEUED (Django-owned transition).
            transition(session, ProcessingState.QUEUED, request=request, actor=actor,
                       source="django", reason="enqueue")
    except IntegrityError:
        # Lost the race against the partial unique index.
        raise SessionError("duplicate_active_session",
                           "an active processing session already exists for this video",
                           status=409)

    observability.record_requested()
    session.refresh_from_db()
    return session


def retry_session(session: ProcessingSession, *, request=None, actor=None) -> ProcessingSession:
    """Create a NEW session linked to a terminal one (original stays immutable, §24)."""
    session = ProcessingSession.objects.get(pk=session.pk)  # fresh state
    if not session.is_terminal:
        raise SessionError("not_terminal", "only terminal sessions can be retried", status=409)

    if settings.CV_BLOCK_DUPLICATE_ACTIVE:
        if ProcessingSession.objects.filter(
            video_asset_id=session.video_asset_id, state__in=NON_TERMINAL_STATES
        ).exists():
            raise SessionError("duplicate_active_session",
                               "an active processing session already exists for this video",
                               status=409)
    try:
        with transaction.atomic():
            new = ProcessingSession.objects.create(
                video_asset_id=session.video_asset_id,
                camera_id=session.camera_id,
                requested_by=actor,
                config_snapshot=session.config_snapshot,  # reuse deduped snapshot
                processing_params=session.processing_params,
                retry_of=session,
                retry_count=session.retry_count + 1,
                state=ProcessingState.CREATED,
            )
            record_audit(
                EventType.PROCESSING_RETRY_REQUESTED, "processing.retry",
                request=request, actor=actor, source="django",
                target_type="ProcessingSession", target_id=str(new.id),
                metadata={"retry_of": str(session.id), "video_id": str(session.video_asset_id)},
            )
            transition(new, ProcessingState.QUEUED, request=request, actor=actor,
                       source="django", reason="retry_enqueue")
    except IntegrityError:
        raise SessionError("duplicate_active_session",
                           "an active processing session already exists for this video",
                           status=409)
    observability.record_requested()
    new.refresh_from_db()
    return new

"""
Processing pipeline orchestrator (Phase 5 §17). Minimal, linear, no AI.

Decode → sample (metadata, before conversion) → FrameProcessor → bounded progress
+ heartbeat → honor pause/resume/stop/cancel at safe frame boundaries → release
frame. Guaranteed cleanup (close source, release GPU, clear heartbeat) in finally.

Expects a session already claimed into INITIALIZING (runtime sets runtime_id).
Postgres is authoritative; Redis heartbeat is a fast mirror.
"""
from __future__ import annotations

import time

import structlog
from django.conf import settings
from django.utils import timezone

from apps.processing import observability
from apps.processing.runtime import heartbeat
from apps.processing.runtime.processors.base import ProcessingContext
from apps.processing.runtime.processors.infra import build_processor
from apps.processing.runtime.sampling import build_sampler
from apps.processing.runtime.video_source import DecoderError, LocalFileSource
from apps.processing.services.state import transition
from apps.processing.states import ProcessingState, RequestedAction

logger = structlog.get_logger("processing")


class _Progress:
    """Throttled progress persister — never writes per frame."""

    def __init__(self, session, *, interval_s: float, every_n: int):
        self.session = session
        self.interval_s = interval_s
        self.every_n = max(1, every_n)
        self._last_time = 0.0
        self._last_frame = 0
        self._t0 = time.perf_counter()

    def _fps(self, decoded, processed):
        elapsed = max(1e-6, time.perf_counter() - self._t0)
        return decoded / elapsed, processed / elapsed

    def maybe(self, *, decoded, processed, meta, total, force=False):
        now = time.perf_counter()
        if not force and (now - self._last_time) < self.interval_s and (decoded - self._last_frame) < self.every_n:
            return
        self._last_time = now
        self._last_frame = decoded
        d_fps, p_fps = self._fps(decoded, processed)
        pct = None
        if total:
            pct = min(100.0, round(100.0 * decoded / total, 2))
        s = self.session
        s.frames_decoded = decoded
        s.frames_processed = processed
        if meta is not None:
            s.current_frame_index = meta.source_frame_index
            s.current_pts_seconds = meta.timestamp_seconds
        s.progress_percent = pct
        s.decode_fps = round(d_fps, 2)
        s.processing_fps = round(p_fps, 2)
        s.last_heartbeat_at = timezone.now()
        s.save(update_fields=[
            "frames_decoded", "frames_processed", "current_frame_index",
            "current_pts_seconds", "progress_percent", "decode_fps",
            "processing_fps", "last_heartbeat_at", "updated_at",
        ])
        heartbeat.write_session_heartbeat(s.id)
        if d_fps:
            observability.observe_decode_fps(round(d_fps, 2))
        if p_fps:
            observability.observe_throughput_fps(round(p_fps, 2))


def _read_action(session_id) -> str:
    from apps.processing.models import ProcessingSession
    return (ProcessingSession.objects
            .filter(pk=session_id).values_list("requested_action", flat=True).first()
            or RequestedAction.NONE)


def run_session(session, *, gpu_manager=None, shutdown=None, redis_client=None) -> str:
    """Run one claimed session to a terminal state. Returns the terminal state.

    `shutdown` is an optional callable → truthy when the runtime is stopping
    (graceful Ctrl+C): the loop exits at the next boundary leaving the session in a
    safe state (the watchdog will FAIL it if the process dies)."""
    from apps.processing.models import ProcessingSession

    session = ProcessingSession.objects.get(pk=session.pk)
    if session.state != ProcessingState.INITIALIZING:
        raise ValueError(f"run_session requires INITIALIZING, got {session.state}")

    snapshot_payload = session.config_snapshot.payload
    params = session.processing_params or {}
    source = None
    owner = f"{session.runtime_id}:{session.id}"
    device = "cpu"

    def _stopping() -> bool:
        return bool(shutdown and shutdown())

    try:
        # Resolve the stored file path (internal only) and open the decoder.
        from apps.ingestion.storage import get_storage_backend
        backend = get_storage_backend()
        try:
            path = backend.resolve_path(session.video_asset.storage_key)
        except Exception as exc:
            return _fail(session, "storage_file_missing", str(exc))
        import os
        if not os.path.exists(path):
            return _fail(session, "storage_file_missing", "file not found")

        if gpu_manager is not None:
            device = gpu_manager.select_device(params.get("device_preference", "auto"))
            gpu_manager.reserve(device, owner)

        source = LocalFileSource(path, source_fps=session.video_asset.fps)
        try:
            source.open()
        except DecoderError as exc:
            return _fail(session, exc.code, str(exc))

        meta_info = source.metadata()
        total = session.frames_total_estimate
        if total is None:
            fc = session.video_asset.frame_count
            if fc and fc > 0:
                total = fc
            elif meta_info.duration_s and meta_info.fps:
                total = int(round(meta_info.duration_s * meta_info.fps))

        transition(session, ProcessingState.RUNNING, source="cv_runtime",
                   extra_fields={"device": device,
                                 "frames_total_estimate": total})
        session.refresh_from_db()

        sampler = build_sampler(params)
        processor = build_processor(params.get("processor", "noop"))
        ctx = ProcessingContext(snapshot_payload=snapshot_payload, params=params,
                                device=device, logger=logger,
                                session_id=session.id, video_id=session.video_asset_id)
        processor.setup(ctx)

        progress = _Progress(session, interval_s=settings.CV_PROGRESS_INTERVAL_SECONDS,
                             every_n=settings.CV_PROGRESS_EVERY_N_FRAMES)
        decoded = 0
        processed = 0
        last_meta = None
        last_action_check = 0.0

        for view in source.frames():
            decoded += 1
            last_meta = view.meta
            if sampler.accept(view.meta):
                processed += 1
                view.meta.processed_index = processed - 1
                processor.process(view, ctx)
            view.release()

            # Bounded progress + heartbeat.
            progress.maybe(decoded=decoded, processed=processed, meta=last_meta, total=total)

            # Command check at a bounded cadence (not every frame).
            now = time.perf_counter()
            if (now - last_action_check) >= 0.4:
                last_action_check = now
                action = _read_action(session.id)
                if action == RequestedAction.CANCEL:
                    return _cancel(session)
                if action == RequestedAction.STOP:
                    return _stop(session, processed, total, progress, last_meta, decoded)
                if action == RequestedAction.PAUSE:
                    paused_result = _pause_and_wait(session, shutdown=shutdown)
                    if paused_result is not None:
                        return paused_result  # cancelled/stopped/shutdown during pause
            if _stopping():
                # Graceful runtime shutdown: leave RUNNING with fresh checkpoint.
                progress.maybe(decoded=decoded, processed=processed, meta=last_meta,
                               total=total, force=True)
                logger.info("processing_runtime_shutdown_midrun", session_id=str(session.id))
                return session.state

        # Completed all frames.
        progress.maybe(decoded=decoded, processed=processed, meta=last_meta, total=total, force=True)
        processor.teardown()
        transition(session, ProcessingState.COMPLETING, source="cv_runtime")
        result = transition(session, ProcessingState.COMPLETED, source="cv_runtime",
                            extra_fields={"progress_percent": 100.0})
        return result.state
    except Exception as exc:  # unexpected → conservative FAIL
        logger.error("processing_pipeline_error", session_id=str(session.pk), error=str(exc)[:200])
        return _fail(session, "runtime_error", str(exc))
    finally:
        if source is not None:
            source.close()
        if gpu_manager is not None:
            gpu_manager.release(owner)
        heartbeat.clear_session_heartbeat(session.pk, redis_client=redis_client)


def _pause_and_wait(session, *, shutdown=None):
    """Transition RUNNING→PAUSING→PAUSED and block until RESUME/STOP/CANCEL/shutdown.
    Returns a terminal state string if it ends here, else None to resume."""
    transition(session, ProcessingState.PAUSING, source="cv_runtime")
    transition(session, ProcessingState.PAUSED, source="cv_runtime")
    while True:
        if shutdown and shutdown():
            return session.state  # stay PAUSED; watchdog reconciles if process dies
        action = _read_action(session.id)
        if action == RequestedAction.RESUME:
            transition(session, ProcessingState.RESUMING, source="cv_runtime")
            transition(session, ProcessingState.RUNNING, source="cv_runtime")
            _clear_action(session.id)
            return None
        if action == RequestedAction.CANCEL:
            return _cancel(session)
        if action == RequestedAction.STOP:
            return _stop(session, session.frames_processed, session.frames_total_estimate, None, None, session.frames_decoded)
        heartbeat.write_session_heartbeat(session.id)
        time.sleep(settings.CV_RUNTIME_POLL_SECONDS)


def _clear_action(session_id) -> None:
    from apps.processing.models import ProcessingSession
    ProcessingSession.objects.filter(pk=session_id).update(requested_action=RequestedAction.NONE)


def _cancel(session) -> str:
    return transition(session, ProcessingState.CANCELLED, source="cv_runtime",
                      reason="cancel_requested").state


def _stop(session, processed, total, progress, meta, decoded) -> str:
    if progress is not None:
        progress.maybe(decoded=decoded, processed=processed, meta=meta, total=total, force=True)
    return transition(session, ProcessingState.STOPPED, source="cv_runtime",
                      reason="stop_requested").state


def _fail(session, code: str, message: str) -> str:
    from apps.processing.services.state import InvalidTransition
    try:
        return transition(session, ProcessingState.FAILED, source="cv_runtime",
                          error_code=code, error_message=message).state
    except InvalidTransition:
        # Already terminal — nothing to do.
        session.refresh_from_db()
        return session.state

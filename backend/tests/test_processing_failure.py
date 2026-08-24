"""Phase 5 — cancellation, stop, pause/resume logic, watchdog, GPU, retention, decoder failure."""
from __future__ import annotations

import pytest

from apps.processing.models import ProcessingSession
from apps.processing.runtime.gpu import GPUManager, detect_devices
from apps.processing.runtime.pipeline import _pause_and_wait, run_session
from apps.processing.services.claim import claim_next
from apps.processing.services import commands
from apps.processing.services.session import create_session
from apps.processing.services.state import transition
from apps.processing.states import ProcessingState, RequestedAction
from tests._processing_helpers import make_valid_video

pytestmark = pytest.mark.django_db


def _claimed(video, operator, params=None):
    create_session(video_id=video.id, params=params, actor=operator)
    return claim_next("test-runtime")


# ---------------- Cancellation / stop (real) ----------------

def test_running_cancel_stops_processing(vstorage, operator):
    video = make_valid_video(fps=30, seconds=2.0)  # 60 frames
    claimed = _claimed(video, operator, {"processor": "framecount"})
    # Request cancel before the loop runs; the boundary check must honor it.
    ProcessingSession.objects.filter(pk=claimed.pk).update(requested_action=RequestedAction.CANCEL)
    state = run_session(claimed)
    assert state == ProcessingState.CANCELLED
    s = ProcessingSession.objects.get(pk=claimed.pk)
    assert s.frames_processed < 60  # actually stopped early, did not run to completion


def test_running_stop_is_terminal(vstorage, operator):
    video = make_valid_video(fps=30, seconds=2.0)
    claimed = _claimed(video, operator, {"processor": "noop"})
    ProcessingSession.objects.filter(pk=claimed.pk).update(requested_action=RequestedAction.STOP)
    state = run_session(claimed)
    assert state == ProcessingState.STOPPED


def test_pause_wait_resumes(vstorage, operator):
    video = make_valid_video()
    claimed = _claimed(video, operator)
    transition(claimed, ProcessingState.RUNNING)
    # Preload RESUME so the wait loop returns immediately (no real blocking).
    ProcessingSession.objects.filter(pk=claimed.pk).update(requested_action=RequestedAction.RESUME)
    result = _pause_and_wait(claimed, shutdown=lambda: False)
    assert result is None  # resumed
    s = ProcessingSession.objects.get(pk=claimed.pk)
    assert s.state == ProcessingState.RUNNING
    assert s.paused_at is not None  # it did pass through PAUSED


def test_pause_wait_cancel(vstorage, operator):
    video = make_valid_video()
    claimed = _claimed(video, operator)
    transition(claimed, ProcessingState.RUNNING)
    ProcessingSession.objects.filter(pk=claimed.pk).update(requested_action=RequestedAction.CANCEL)
    result = _pause_and_wait(claimed, shutdown=lambda: False)
    assert result == ProcessingState.CANCELLED


# ---------------- Command service guards ----------------

def test_cancel_running_sets_action(vstorage, operator):
    video = make_valid_video()
    claimed = _claimed(video, operator)  # INITIALIZING
    commands.request_cancel(claimed, actor=operator)
    s = ProcessingSession.objects.get(pk=claimed.pk)
    assert s.requested_action == RequestedAction.CANCEL
    assert s.cancel_requested_at is not None
    assert s.state == ProcessingState.INITIALIZING  # runtime performs the actual transition


def test_resume_requires_paused(vstorage, operator):
    from apps.processing.services.session import SessionError
    video = make_valid_video()
    claimed = _claimed(video, operator)
    with pytest.raises(SessionError) as exc:
        commands.request_resume(claimed, actor=operator)
    assert exc.value.code == "not_paused"


# ---------------- Watchdog / stale recovery ----------------

def test_watchdog_fails_stale_session(vstorage, operator, settings):
    from datetime import timedelta
    from django.utils import timezone
    from apps.processing.tasks import reconcile_stale_sessions

    video = make_valid_video()
    claimed = _claimed(video, operator)
    transition(claimed, ProcessingState.RUNNING)
    # Simulate a crash: stale DB heartbeat, no Redis heartbeat.
    old = timezone.now() - timedelta(seconds=settings.CV_STALE_SESSION_SECONDS + 60)
    ProcessingSession.objects.filter(pk=claimed.pk).update(last_heartbeat_at=old)
    failed = reconcile_stale_sessions()
    assert failed >= 1
    s = ProcessingSession.objects.get(pk=claimed.pk)
    assert s.state == ProcessingState.FAILED
    assert s.error_code == "heartbeat_lost"


def test_watchdog_ignores_fresh_session(vstorage, operator):
    from django.utils import timezone
    from apps.processing.tasks import reconcile_stale_sessions
    video = make_valid_video()
    claimed = _claimed(video, operator)
    transition(claimed, ProcessingState.RUNNING)
    ProcessingSession.objects.filter(pk=claimed.pk).update(last_heartbeat_at=timezone.now())
    reconcile_stale_sessions()
    assert ProcessingSession.objects.get(pk=claimed.pk).state == ProcessingState.RUNNING


# ---------------- Duplicate execution prevention ----------------

def test_claim_is_exclusive(vstorage, operator):
    video = make_valid_video()
    create_session(video_id=video.id, params=None, actor=operator)
    first = claim_next("runtime-A")
    second = claim_next("runtime-B")
    assert first is not None
    assert second is None  # already claimed / no other queued


# ---------------- GPU manager (real hardware, no torch) ----------------

def test_gpu_detect_real_environment():
    st = detect_devices()
    assert st.mode in ("cuda", "cpu")
    if st.available:
        assert st.devices and all(d.name for d in st.devices)  # no fake device


def test_gpu_select_and_reserve_cpu():
    mgr = GPUManager()
    dev = mgr.select_device("cpu")
    assert dev == "cpu"
    assert mgr.reserve(dev, "owner-1") is True
    assert mgr.can_fit(999999, "cpu") is True


def test_gpu_unavailable_falls_back_to_cpu(monkeypatch):
    import apps.processing.runtime.gpu as gpumod
    monkeypatch.setattr(gpumod.shutil, "which", lambda name: None)  # no nvidia-smi
    st = gpumod.detect_devices()
    assert st.available is False and st.mode == "cpu" and st.detector == "none"


# ---------------- Retention protection ----------------

def test_active_session_protects_video(vstorage, operator):
    from apps.ingestion.retention_handlers import _video_is_protected
    video = make_valid_video()
    create_session(video_id=video.id, params=None, actor=operator)  # QUEUED (non-terminal)
    assert _video_is_protected(video) is True


def test_terminal_session_does_not_protect(vstorage, operator):
    from apps.ingestion.retention_handlers import _video_is_protected
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)
    transition(s, ProcessingState.CANCELLED)
    assert _video_is_protected(video) is False


# ---------------- Decoder unavailable ----------------

def test_decoder_unavailable_fails_session(vstorage, operator, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "av":
            raise ImportError("simulated: no av")
        return real_import(name, *a, **k)

    video = make_valid_video()
    claimed = _claimed(video, operator)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    state = run_session(claimed)
    assert state == ProcessingState.FAILED
    s = ProcessingSession.objects.get(pk=claimed.pk)
    assert s.error_code == "decoder_unavailable"

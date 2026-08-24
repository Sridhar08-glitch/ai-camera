"""Phase 5 — ProcessingSession, snapshot, and state-machine tests."""
from __future__ import annotations

import pytest

from apps.processing.models import ProcessingConfigSnapshot
from apps.processing.services.session import SessionError, create_session, retry_session
from apps.processing.services.snapshot import build_payload, capture_snapshot
from apps.processing.services.state import InvalidTransition, transition
from apps.processing.states import ProcessingState
from tests._processing_helpers import make_camera_with_config, make_valid_video

pytestmark = pytest.mark.django_db


# ---------------- Snapshot ----------------

def test_snapshot_deterministic_and_hashed(vstorage):
    cam, _ = make_camera_with_config()
    video = make_valid_video(camera=cam)
    s1 = capture_snapshot(video)
    p2 = build_payload(video)
    from apps.common.versioning import canonical_hash
    assert s1.snapshot_hash == canonical_hash(p2)  # deterministic
    assert s1.payload["camera"]["id"] == str(cam.id)
    assert len(s1.payload["rois"]) == 1
    assert len(s1.payload["counting_lines"]) == 1
    assert len(s1.payload["stop_lines"]) == 1


def test_snapshot_dedup_by_hash(vstorage):
    cam, _ = make_camera_with_config()
    v1 = make_valid_video(camera=cam)
    # Two videos with identical camera config but different video identity produce
    # different snapshots (video identity is part of the payload).
    s1 = capture_snapshot(v1)
    s1b = capture_snapshot(v1)
    assert s1.id == s1b.id  # same video → reused row
    assert ProcessingConfigSnapshot.objects.count() == 1


def test_snapshot_immutable(vstorage):
    cam, _ = make_camera_with_config()
    snap = capture_snapshot(make_valid_video(camera=cam))
    snap.snapshot_schema_version = 99
    with pytest.raises(ValueError):
        snap.save()


def test_snapshot_unaffected_by_later_config_change(vstorage):
    cam, lane = make_camera_with_config()
    video = make_valid_video(camera=cam)
    snap = capture_snapshot(video)
    original_hash = snap.snapshot_hash
    roi_rev_before = snap.payload["rois"][0]["revision"]
    # Mutate the live ROI geometry after capture.
    roi = cam.rois.first()
    roi.polygon = {"space": "image_normalized", "coordinates": [[0.2, 0.2], [0.8, 0.2], [0.5, 0.8]]}
    roi.save()
    assert roi.revision == roi_rev_before + 1  # live entity bumped
    snap.refresh_from_db()
    assert snap.snapshot_hash == original_hash  # snapshot NOT mutated
    assert snap.payload["rois"][0]["revision"] == roi_rev_before


def test_snapshot_excludes_secrets_and_pii(vstorage):
    cam, _ = make_camera_with_config()
    payload = build_payload(make_valid_video(camera=cam))
    import json
    blob = json.dumps(payload).lower()
    for banned in ("password", "secret", "token", "email", "@example"):
        assert banned not in blob


def test_snapshot_without_camera(vstorage):
    video = make_valid_video(camera=None)
    snap = capture_snapshot(video)
    assert snap.payload["camera"] is None
    assert snap.payload["video"]["video_asset_id"] == str(video.id)


# ---------------- Session creation ----------------

def test_create_session_queues_and_snapshots(vstorage, operator):
    cam, _ = make_camera_with_config()
    video = make_valid_video(camera=cam)
    session = create_session(video_id=video.id, params={"sampling": {"mode": "every_frame"}},
                             actor=operator)
    assert session.state == ProcessingState.QUEUED
    assert session.queued_at is not None
    assert session.config_snapshot_id is not None
    assert session.camera_id == cam.id


def test_create_rejects_invalid_video(vstorage, operator):
    from apps.ingestion.models import ValidationStatus
    video = make_valid_video()
    video.validation_status = ValidationStatus.INVALID
    video.save()
    with pytest.raises(SessionError) as exc:
        create_session(video_id=video.id, params=None, actor=operator)
    assert exc.value.code == "video_not_valid"


def test_create_rejects_duplicate_active(vstorage, operator):
    video = make_valid_video()
    create_session(video_id=video.id, params=None, actor=operator)
    with pytest.raises(SessionError) as exc:
        create_session(video_id=video.id, params=None, actor=operator)
    assert exc.value.code == "duplicate_active_session"


def test_create_rejects_bad_params(vstorage, operator):
    from apps.processing.services.params import ParamsError
    video = make_valid_video()
    with pytest.raises(ParamsError):
        create_session(video_id=video.id, params={"sampling": {"mode": "bogus"}}, actor=operator)


# ---------------- State machine ----------------

def test_valid_transition_path(vstorage, operator):
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)
    transition(s, ProcessingState.INITIALIZING)
    transition(s, ProcessingState.RUNNING)
    transition(s, ProcessingState.COMPLETING)
    result = transition(s, ProcessingState.COMPLETED)
    assert result.state == ProcessingState.COMPLETED
    assert result.completed_at is not None


def test_forbidden_transition_rejected(vstorage, operator):
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)  # QUEUED
    with pytest.raises(InvalidTransition):
        transition(s, ProcessingState.RUNNING)  # must go through INITIALIZING


def test_terminal_is_immutable(vstorage, operator):
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)
    transition(s, ProcessingState.CANCELLED)
    with pytest.raises(InvalidTransition):
        transition(s, ProcessingState.INITIALIZING)


def test_idempotent_same_state(vstorage, operator):
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)
    transition(s, ProcessingState.CANCELLED)
    # Re-issuing the same terminal state is a no-op, not an error.
    again = transition(s, ProcessingState.CANCELLED)
    assert again.state == ProcessingState.CANCELLED


def test_retry_creates_new_linked_session(vstorage, operator):
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)
    transition(s, ProcessingState.INITIALIZING)
    transition(s, ProcessingState.FAILED, error_code="runtime_error")
    new = retry_session(s, actor=operator)
    assert new.id != s.id
    assert new.retry_of_id == s.id
    assert new.retry_count == 1
    assert new.state == ProcessingState.QUEUED
    s.refresh_from_db()
    assert s.state == ProcessingState.FAILED  # original immutable
    assert new.config_snapshot_id == s.config_snapshot_id  # snapshot reused


def test_retry_requires_terminal(vstorage, operator):
    video = make_valid_video()
    s = create_session(video_id=video.id, params=None, actor=operator)
    with pytest.raises(SessionError) as exc:
        retry_session(s, actor=operator)
    assert exc.value.code == "not_terminal"

"""Phase 5 — API contract + permission matrix + command endpoints."""
from __future__ import annotations

import pytest

from apps.common.roles import RoleCode
from apps.processing.states import ProcessingState
from tests._processing_helpers import make_valid_video

pytestmark = pytest.mark.django_db

BASE = "/api/v1/processing-sessions"


@pytest.fixture
def analyst(make_user):
    return make_user(RoleCode.TRAFFIC_ANALYST)


def _create(api, auth, user, video):
    return auth(api, user).post(BASE, {"video_id": str(video.id)}, format="json")


def test_operator_can_create_and_list(api, auth, operator, vstorage):
    video = make_valid_video()
    r = _create(api, auth, operator, video)
    assert r.status_code == 201, r.data
    assert r.data["state"] == ProcessingState.QUEUED
    assert "snapshot_hash" in r.data
    lst = auth(api, operator).get(BASE)
    assert lst.status_code == 200
    assert lst.data["meta"]["pagination"]["count"] == 1


def test_viewer_excluded(api, auth, viewer, vstorage):
    video = make_valid_video()
    assert _create(api, auth, viewer, video).status_code == 403
    assert auth(api, viewer).get(BASE).status_code == 403


def test_analyst_read_only(api, auth, analyst, operator, vstorage):
    video = make_valid_video()
    _create(api, auth, operator, video)
    # analyst can read
    assert auth(api, analyst).get(BASE).status_code == 200
    # analyst cannot create (distinct video to avoid checksum-dedup collision)
    assert _create(api, auth, analyst, make_valid_video(seconds=2.0)).status_code == 403


def test_create_rejects_invalid_params(api, auth, operator, vstorage):
    video = make_valid_video()
    r = auth(api, operator).post(
        BASE, {"video_id": str(video.id), "sampling": {"mode": "nope"}}, format="json")
    assert r.status_code == 400
    assert r.data["error"]["code"] == "invalid_params"


def test_duplicate_active_conflict(api, auth, operator, vstorage):
    video = make_valid_video()
    assert _create(api, auth, operator, video).status_code == 201
    r = _create(api, auth, operator, video)
    assert r.status_code == 409
    assert r.data["error"]["code"] == "duplicate_active_session"


def test_cancel_pre_pickup(api, auth, operator, vstorage):
    video = make_valid_video()
    sid = _create(api, auth, operator, video).data["id"]
    r = auth(api, operator).post(f"{BASE}/{sid}/cancel")
    assert r.status_code == 200
    assert r.data["state"] == ProcessingState.CANCELLED


def test_pause_requires_running(api, auth, operator, vstorage):
    video = make_valid_video()
    sid = _create(api, auth, operator, video).data["id"]
    r = auth(api, operator).post(f"{BASE}/{sid}/pause")
    assert r.status_code == 409
    assert r.data["error"]["code"] == "not_running"


def test_snapshot_metadata_endpoint(api, auth, operator, vstorage):
    from tests._processing_helpers import make_camera_with_config
    cam, _ = make_camera_with_config()
    video = make_valid_video(camera=cam)
    sid = _create(api, auth, operator, video).data["id"]
    r = auth(api, operator).get(f"{BASE}/{sid}/snapshot")
    assert r.status_code == 200
    assert "snapshot_hash" in r.data
    assert r.data["counts"]["rois"] == 1
    # No raw geometry dump by default.
    assert "polygon" not in str(r.data)


def test_retry_via_api(api, auth, operator, vstorage):
    from apps.processing.models import ProcessingSession
    from apps.processing.services.state import transition
    video = make_valid_video()
    sid = _create(api, auth, operator, video).data["id"]
    s = ProcessingSession.objects.get(id=sid)
    transition(s, ProcessingState.CANCELLED)
    r = auth(api, operator).post(f"{BASE}/{sid}/retry")
    assert r.status_code == 201
    assert r.data["retry_of"] == sid
    assert r.data["state"] == ProcessingState.QUEUED


def test_runtime_status_endpoint(api, auth, operator, vstorage):
    r = auth(api, operator).get("/api/v1/processing/runtime-status")
    assert r.status_code == 200
    assert "cv_runtime_available" in r.data
    assert "gpu" in r.data and "mode" in r.data["gpu"]


def test_state_not_settable_via_api(api, auth, operator, vstorage):
    """POSTing a state field must not change session state (state is runtime-owned)."""
    video = make_valid_video()
    r = auth(api, operator).post(
        BASE, {"video_id": str(video.id), "state": "running"}, format="json")
    assert r.status_code == 201
    assert r.data["state"] == ProcessingState.QUEUED  # ignored

"""Phase 6 — detections API contract + permission matrix.

viewer / incident_operator are excluded from processing resources (privacy §32);
analyst reads; operator/admin control. Detections are read-only and surface the
`is_test_provider` flag the frontend uses for the TEST-provider banner.
"""
from __future__ import annotations

import pytest

from apps.common.roles import RoleCode
from apps.processing.runtime.pipeline import run_session
from apps.processing.services.claim import claim_next
from apps.processing.services.session import create_session
from tests._processing_helpers import make_valid_video

pytestmark = pytest.mark.django_db

BASE = "/api/v1/processing-sessions"


@pytest.fixture
def analyst(make_user):
    return make_user(RoleCode.TRAFFIC_ANALYST)


@pytest.fixture
def incident_operator(make_user):
    return make_user(RoleCode.INCIDENT_OPERATOR)


def _make_detector_session(video, operator):
    session = create_session(
        video_id=video.id,
        params={"processor": "detector", "sampling": {"mode": "every_frame"},
                "detector": {"model_version_id": "test"}},
        actor=operator,
    )
    claimed = claim_next("test-runtime")
    run_session(claimed)
    return session


def test_detections_list_and_filter(api, auth, operator, vstorage):
    video = make_valid_video(fps=6, seconds=1.0)
    session = _make_detector_session(video, operator)
    url = f"{BASE}/{session.id}/detections"
    r = auth(api, operator).get(url)
    assert r.status_code == 200
    assert r.data["meta"]["pagination"]["count"] == 6
    first = r.data["data"][0]
    assert first["is_test_provider"] is True
    assert first["provider_name"] == "test"
    assert "detections" in first

    # filter by a single frame index
    r2 = auth(api, operator).get(url + "?frame=2")
    assert r2.status_code == 200
    assert r2.data["meta"]["pagination"]["count"] == 1
    assert r2.data["data"][0]["source_frame_index"] == 2


def test_detection_frame_detail_and_404(api, auth, operator, vstorage):
    video = make_valid_video(fps=5, seconds=1.0)
    session = _make_detector_session(video, operator)
    r = auth(api, operator).get(f"{BASE}/{session.id}/detections/0")
    assert r.status_code == 200
    assert r.data["source_frame_index"] == 0
    # A frame index that was never processed → 404.
    assert auth(api, operator).get(f"{BASE}/{session.id}/detections/999").status_code == 404


def test_detections_analyst_can_read(api, auth, operator, analyst, vstorage):
    video = make_valid_video(fps=4, seconds=1.0)
    session = _make_detector_session(video, operator)
    assert auth(api, analyst).get(f"{BASE}/{session.id}/detections").status_code == 200


def test_detections_viewer_excluded(api, auth, operator, viewer, incident_operator, vstorage):
    video = make_valid_video(fps=4, seconds=1.0)
    session = _make_detector_session(video, operator)
    url = f"{BASE}/{session.id}/detections"
    assert auth(api, viewer).get(url).status_code == 403
    assert auth(api, incident_operator).get(url).status_code == 403


def test_detections_requires_auth(api, operator, vstorage):
    video = make_valid_video(fps=4, seconds=1.0)
    session = _make_detector_session(video, operator)
    assert api.get(f"{BASE}/{session.id}/detections").status_code in (401, 403)

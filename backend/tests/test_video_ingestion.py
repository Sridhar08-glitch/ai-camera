"""Video ingestion API tests (Phase 4): upload, validate, metadata, thumbnail, perms."""
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditEvent, EventType
from apps.common.roles import RoleCode
from apps.ingestion.models import ValidationStatus, VideoAsset
from tests._video_fixtures import make_test_video_bytes

pytestmark = pytest.mark.django_db


def _video_file(name="clip.mp4", content=None):
    return SimpleUploadedFile(name, content if content is not None else make_test_video_bytes(),
                              content_type="video/mp4")


def _upload(api, **extra):
    data = {"file": _video_file(), **extra}
    return api.post("/api/v1/videos", data, format="multipart")


def test_valid_upload_stores_and_probes(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    resp = _upload(api)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["validation_status"] == ValidationStatus.VALID
    assert data["codec"] == "mpeg4"
    assert data["width"] == 64 and data["height"] == 48
    assert data["has_thumbnail"] is True
    # storage paths never exposed
    assert "storage_key" not in data and "stored_artifact" not in data
    asset = VideoAsset.objects.get(id=data["id"])
    assert asset.stored_artifact.checksum_sha256 == asset.checksum_sha256


def test_upload_is_audited(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    _upload(api)
    assert AuditEvent.objects.filter(event_type=EventType.VIDEO_UPLOADED).exists()


def test_zero_byte_rejected(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    resp = api.post("/api/v1/videos", {"file": _video_file(content=b"")}, format="multipart")
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "empty_file"


def test_non_video_rejected(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    resp = api.post("/api/v1/videos", {"file": _video_file(name="x.mp4", content=b"not a video at all!!")}, format="multipart")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_container"


def test_oversized_rejected(api, auth, sysadmin, vstorage, settings):
    settings.MAX_UPLOAD_BYTES = 100  # tiny
    auth(api, sysadmin)
    resp = _upload(api)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "file_too_large"


def test_duplicate_rejected(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    content = make_test_video_bytes()
    first = api.post("/api/v1/videos", {"file": _video_file(content=content)}, format="multipart")
    assert first.status_code == 201
    dup = api.post("/api/v1/videos", {"file": _video_file(content=content)}, format="multipart")
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "duplicate_video"
    assert dup.json()["error"]["existing_id"] == first.json()["data"]["id"]


def test_metadata_endpoint(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    vid = _upload(api).json()["data"]["id"]
    resp = api.get(f"/api/v1/videos/{vid}/metadata")
    assert resp.status_code == 200
    assert resp.json()["data"]["codec"] == "mpeg4"


def test_thumbnail_endpoint_returns_jpeg(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    vid = _upload(api).json()["data"]["id"]
    resp = api.get(f"/api/v1/videos/{vid}/thumbnail")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/jpeg"
    assert b"".join(resp.streaming_content)[:3] == b"\xff\xd8\xff"


def test_archive_deactivates(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    vid = _upload(api).json()["data"]["id"]
    resp = api.post(f"/api/v1/videos/{vid}/archive")
    assert resp.status_code == 200
    assert VideoAsset.objects.get(id=vid).is_active is False


def test_archive_frees_duplicate_slot(api, auth, sysadmin, vstorage):
    auth(api, sysadmin)
    content = make_test_video_bytes()
    v1 = api.post("/api/v1/videos", {"file": _video_file(content=content)}, format="multipart").json()["data"]["id"]
    api.post(f"/api/v1/videos/{v1}/archive")
    # after archive, the same content may be uploaded again
    v2 = api.post("/api/v1/videos", {"file": _video_file(content=content)}, format="multipart")
    assert v2.status_code == 201


def test_hard_delete_removes_files(api, auth, sysadmin, vstorage, django_capture_on_commit_callbacks):
    from apps.ingestion.storage import get_storage_backend

    auth(api, sysadmin)
    data = _upload(api).json()["data"]
    asset = VideoAsset.objects.get(id=data["id"])
    key = asset.storage_key
    backend = get_storage_backend()
    assert backend.exists(key)
    with django_capture_on_commit_callbacks(execute=True):
        resp = api.delete(f"/api/v1/videos/{data['id']}")
    assert resp.status_code == 204
    assert not VideoAsset.objects.filter(id=data["id"]).exists()
    assert not backend.exists(key)  # file cleaned up on commit


# ---- permissions ----

def test_operator_can_upload(api, auth, make_user, vstorage):
    auth(api, make_user(RoleCode.TRAFFIC_OPERATOR))
    assert _upload(api).status_code == 201


def test_analyst_cannot_upload_but_can_read(api, auth, make_user, sysadmin, vstorage):
    # sysadmin uploads
    auth(api, sysadmin)
    vid = _upload(api).json()["data"]["id"]
    # analyst may read, not upload
    auth(api, make_user(RoleCode.TRAFFIC_ANALYST))
    assert api.get(f"/api/v1/videos/{vid}").status_code == 200
    assert _upload(api).status_code == 403


def test_viewer_denied_all_video_access(api, auth, make_user, sysadmin, vstorage):
    auth(api, sysadmin)
    vid = _upload(api).json()["data"]["id"]
    auth(api, make_user(RoleCode.VIEWER))
    assert api.get("/api/v1/videos").status_code == 403
    assert api.get(f"/api/v1/videos/{vid}").status_code == 403
    assert api.get(f"/api/v1/videos/{vid}/thumbnail").status_code == 403


def test_only_sysadmin_hard_deletes(api, auth, traffic_admin, sysadmin, vstorage):
    auth(api, sysadmin)
    vid = _upload(api).json()["data"]["id"]
    auth(api, traffic_admin)
    assert api.delete(f"/api/v1/videos/{vid}").status_code == 403


def test_unauthenticated_denied(api, vstorage):
    assert api.get("/api/v1/videos").status_code == 401

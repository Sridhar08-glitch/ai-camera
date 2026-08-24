"""Video ingestion failure-path tests (Phase 4 §28). No fake success."""
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.audit.models import AuditEvent, EventType
from apps.ingestion.models import ValidationStatus, VideoAsset
from apps.ingestion.probe import ProbeError
from tests._video_fixtures import make_test_video_bytes

pytestmark = pytest.mark.django_db


def _upload(api, content=None):
    f = SimpleUploadedFile("clip.mp4", content or make_test_video_bytes(), content_type="video/mp4")
    return api.post("/api/v1/videos", {"file": f}, format="multipart")


def test_decoder_unavailable_marks_invalid(api, auth, sysadmin, vstorage, monkeypatch):
    def boom(path):
        raise ProbeError("decoder_unavailable", "no decoder")

    monkeypatch.setattr("apps.ingestion.ingest.probe_video", boom)
    auth(api, sysadmin)
    resp = _upload(api)
    # asset row is created but marked invalid — never a fake "valid"
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["validation_status"] == ValidationStatus.INVALID
    assert data["error_code"] == "decoder_unavailable"
    assert AuditEvent.objects.filter(event_type=EventType.VIDEO_VALIDATION_FAILED).exists()


def test_corrupt_video_marked_invalid(api, auth, sysadmin, vstorage):
    # a valid MP4 container header but truncated/garbage payload
    good = make_test_video_bytes()
    corrupt = good[:12] + b"\x00" * 200  # keep ftyp sniff, break the stream
    auth(api, sysadmin)
    resp = _upload(api, content=corrupt)
    # signature sniff passes; probe fails -> invalid (or rejected), never valid
    if resp.status_code == 201:
        assert resp.json()["data"]["validation_status"] in (ValidationStatus.INVALID,)
    else:
        assert resp.status_code in (400, 413)


def test_insufficient_disk_rejected(api, auth, sysadmin, vstorage, settings, monkeypatch):
    import apps.ingestion.capacity as cap

    # Report almost no free disk so the reserve check fails.
    monkeypatch.setattr(cap.shutil, "disk_usage", lambda p: type("D", (), {"free": 100})())
    settings.MIN_FREE_DISK_BYTES = 10 ** 12
    auth(api, sysadmin)
    resp = _upload(api)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "insufficient_disk_space"


def test_quota_exceeded_rejected(api, auth, sysadmin, vstorage, settings):
    settings.VIDEO_STORAGE_QUOTA_BYTES = 1  # 1 byte quota
    auth(api, sysadmin)
    resp = _upload(api)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "quota_exceeded"


def test_db_failure_compensates_file(sysadmin, vstorage, monkeypatch):
    import os

    from apps.ingestion import ingest
    from apps.ingestion.storage import get_storage_backend

    # Force the DB row creation to fail after the file is saved.
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(ingest.StoredArtifact.objects, "create", boom)
    upload = SimpleUploadedFile("clip.mp4", make_test_video_bytes(), content_type="video/mp4")

    # Call the service directly so the exception propagates (the API would wrap it in 500).
    with pytest.raises(RuntimeError):
        ingest.ingest_upload(upload, request=None)

    # Compensation: no orphaned file remains and no asset/artifact row exists.
    assert VideoAsset.objects.count() == 0
    root = get_storage_backend().root
    leftover = [f for _d, _s, files in os.walk(root) for f in files]
    assert leftover == []


def test_missing_file_flagged_by_reconcile(api, auth, sysadmin, vstorage):
    from apps.governance.models import ArtifactState, StoredArtifact
    from apps.ingestion.storage import get_storage_backend
    from apps.ingestion.tasks import reconcile_storage

    auth(api, sysadmin)
    data = _upload(api).json()["data"]
    asset = VideoAsset.objects.get(id=data["id"])
    # simulate the backing file disappearing
    get_storage_backend().delete(asset.storage_key)
    result = reconcile_storage()
    assert result["flagged_missing"] >= 1
    art = StoredArtifact.objects.get(id=asset.stored_artifact_id)
    assert art.state == ArtifactState.ORPHANED

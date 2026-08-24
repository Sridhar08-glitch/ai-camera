"""
Ingestion service (Phase 4): stream → checksum → capacity → dedupe → store →
DB (transactional) → probe → thumbnail, with FS/DB compensation.

FS and PostgreSQL are not one transaction. Order: save file to content-addressed
storage FIRST, then create DB rows in a transaction; if the DB transaction fails,
delete the just-saved file (compensation). Probe/thumbnail run after the row
exists; failures mark the asset invalid and schedule file cleanup.
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.audit.models import EventType, Outcome
from apps.audit.services import record_audit
from apps.governance.models import ArtifactState, StoredArtifact
from apps.common.datacategories import DataCategory
from apps.ingestion.capacity import CapacityError, check_upload_allowed
from apps.ingestion.models import ValidationStatus, VideoAsset
from apps.ingestion.probe import ProbeError, make_thumbnail, probe_video, sniff_container
from apps.ingestion.storage import content_key, get_storage_backend


class IngestError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, existing_id=None):
        self.code = code
        self.status = status
        self.existing_id = existing_id
        super().__init__(message)


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]")


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name or "")
    name = _SAFE_NAME.sub("_", name).strip()
    return name[:255] or "upload"


def _stream_to_temp(uploaded_file) -> tuple[str, str, int]:
    """Write the upload to a temp file, returning (temp_path, sha256, size)."""
    Path(settings.VIDEO_TEMP_ROOT).mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=settings.VIDEO_TEMP_ROOT, suffix=".upload")
    h = hashlib.sha256()
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            for chunk in uploaded_file.chunks():
                out.write(chunk)
                h.update(chunk)
                size += len(chunk)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return tmp, h.hexdigest(), size


def ingest_upload(uploaded_file, *, request, camera=None, ext: str = "") -> VideoAsset:
    original = sanitize_filename(getattr(uploaded_file, "name", ""))
    ext = (ext or Path(original).suffix).lstrip(".").lower()

    tmp_path, checksum, size = _stream_to_temp(uploaded_file)
    key = content_key(checksum, ext)
    backend = get_storage_backend()
    saved = False
    try:
        # Pre-persistence validation.
        try:
            check_upload_allowed(size)
        except CapacityError as exc:
            raise IngestError(exc.code, str(exc), status=413) from exc

        with open(tmp_path, "rb") as fh:
            header = fh.read(64)
        sniffed = sniff_container(header)
        if sniffed is None:
            raise IngestError("unsupported_container", "file is not a recognized video container", status=400)

        # Duplicate detection by content checksum (D4).
        dup = VideoAsset.objects.filter(checksum_sha256=checksum, is_active=True).first()
        if dup:
            raise IngestError("duplicate_video", "identical video already exists", status=409, existing_id=str(dup.id))

        # Save to content-addressed storage (idempotent — key derived from checksum).
        if not backend.exists(key):
            backend.save(tmp_path, key)  # moves the temp file into place
        else:
            Path(tmp_path).unlink(missing_ok=True)
        saved = True
        tmp_path = None  # consumed by save()

        # Create DB rows transactionally; compensate the file on failure.
        try:
            with transaction.atomic():
                artifact = StoredArtifact.objects.create(
                    category=DataCategory.RAW_VIDEO, path=key,
                    checksum_sha256=checksum, size_bytes=size, state=ArtifactState.PRESENT,
                )
                asset = VideoAsset.objects.create(
                    original_filename=original, storage_key=key, stored_artifact=artifact,
                    camera=camera, uploaded_by=getattr(request, "user", None),
                    size_bytes=size, checksum_sha256=checksum,
                    mime_detected=sniffed, validation_status=ValidationStatus.PENDING,
                )
        except Exception:
            # Compensation: remove the just-saved file if no other asset references it.
            if not VideoAsset.objects.filter(storage_key=key).exists():
                backend.delete(key)
            raise

        # Probe + optional thumbnail (after the row exists).
        _validate_and_probe(asset, backend)
        record_audit(
            EventType.VIDEO_UPLOADED, action="upload_video", request=request,
            target_type="VideoAsset", target_id=asset.id,
            metadata={"filename": original, "size_bytes": size,
                      "checksum": checksum[:12], "status": asset.validation_status},
        )
        return asset
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        _ = saved


def _validate_and_probe(asset: VideoAsset, backend) -> None:
    path = backend.resolve_path(asset.storage_key)
    try:
        meta = probe_video(path)
    except ProbeError as exc:
        asset.validation_status = ValidationStatus.INVALID
        asset.error_code = exc.code
        asset.error_message = str(exc)[:500]
        asset.save(update_fields=["validation_status", "error_code", "error_message", "updated_at"])
        record_audit(
            EventType.VIDEO_VALIDATION_FAILED, action="validate_video", outcome=Outcome.FAILURE,
            target_type="VideoAsset", target_id=asset.id, metadata={"error_code": exc.code},
        )
        return

    asset.container_format = meta.container_format
    asset.codec = meta.codec
    asset.duration_s = meta.duration_s
    asset.width = meta.width
    asset.height = meta.height
    asset.fps = meta.fps
    asset.frame_count = meta.frame_count
    asset.validation_status = ValidationStatus.VALID

    if settings.VIDEO_THUMBNAIL_ENABLED:
        try:
            jpeg = make_thumbnail(path, settings.VIDEO_THUMBNAIL_MAX_DIM)
            thumb_checksum = hashlib.sha256(jpeg).hexdigest()
            thumb_key = content_key(thumb_checksum, "jpg")
            thumb_path = Path(backend.resolve_path(thumb_key))
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            thumb_path.write_bytes(jpeg)
            thumb_artifact = StoredArtifact.objects.create(
                category=DataCategory.VIDEO_THUMBNAIL, path=thumb_key,
                checksum_sha256=thumb_checksum, size_bytes=len(jpeg), state=ArtifactState.PRESENT,
            )
            asset.thumbnail_artifact = thumb_artifact
            asset.has_thumbnail = True
        except ProbeError:
            asset.has_thumbnail = False  # thumbnail is best-effort; asset stays valid

    asset.save()

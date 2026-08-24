"""VideoAsset — durable record of an ingested recorded video (Phase 4)."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.governance.models import StoredArtifact
from apps.network.models import Camera


class SourceType(models.TextChoices):
    UPLOADED_FILE = "uploaded_file", "Uploaded file"
    # Reserved, inactive — no live-source support in Phase 4.
    RTSP = "rtsp", "RTSP (reserved)"
    WEBCAM = "webcam", "Webcam (reserved)"
    NVR = "nvr", "NVR (reserved)"
    DISK_PATH = "disk_path", "Disk path (reserved)"


class ValidationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VALID = "valid", "Valid"
    INVALID = "invalid", "Invalid"
    QUARANTINED = "quarantined", "Quarantined"


class PrivacyStatus(models.TextChoices):
    RAW_UNPROCESSED = "raw_unprocessed", "Raw / unprocessed"
    ANONYMIZED = "anonymized", "Anonymized (reserved)"


class VideoAsset(UUIDTimeStampedModel):
    # Identity / storage
    original_filename = models.CharField(max_length=255, blank=True, default="")  # display only
    storage_key = models.CharField(max_length=512)  # server-generated (content-addressed)
    stored_artifact = models.ForeignKey(
        StoredArtifact, on_delete=models.PROTECT, related_name="video_assets"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.SET_NULL, null=True, blank=True, related_name="video_assets"
    )
    source_type = models.CharField(max_length=16, choices=SourceType.choices, default=SourceType.UPLOADED_FILE)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # File facts (authoritative source is the StoredArtifact; mirrored read-only here)
    size_bytes = models.BigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)

    # Sniffed / probed
    mime_detected = models.CharField(max_length=64, blank=True, default="")
    container_format = models.CharField(max_length=32, blank=True, default="")
    codec = models.CharField(max_length=32, blank=True, default="")
    duration_s = models.FloatField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    frame_count = models.BigIntegerField(null=True, blank=True)  # best-effort

    # Lifecycle
    validation_status = models.CharField(max_length=16, choices=ValidationStatus.choices, default=ValidationStatus.PENDING)
    is_active = models.BooleanField(default=True)
    error_code = models.CharField(max_length=48, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")

    # Preview
    thumbnail_artifact = models.ForeignKey(
        StoredArtifact, on_delete=models.SET_NULL, null=True, blank=True, related_name="thumbnail_of"
    )
    has_thumbnail = models.BooleanField(default=False)

    # Time provenance (optional; never invented)
    recording_started_at = models.DateTimeField(null=True, blank=True)
    recording_time_source = models.CharField(max_length=32, blank=True, default="")

    # Privacy
    privacy_status = models.CharField(max_length=16, choices=PrivacyStatus.choices, default=PrivacyStatus.RAW_UNPROCESSED)

    class Meta:
        db_table = "ingestion_video_asset"
        ordering = ["-uploaded_at"]
        constraints = [
            # Reject exact-checksum duplicates among active assets (D4).
            models.UniqueConstraint(
                fields=["checksum_sha256"],
                condition=models.Q(is_active=True),
                name="uq_video_active_checksum",
            )
        ]
        indexes = [
            models.Index(fields=["checksum_sha256"]),
            models.Index(fields=["camera", "is_active"]),
            models.Index(fields=["validation_status", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename or self.id} [{self.validation_status}]"

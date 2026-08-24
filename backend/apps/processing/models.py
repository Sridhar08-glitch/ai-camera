"""
Processing domain models (Phase 5 / ADR-024, ADR-026).

- ProcessingConfigSnapshot: immutable, content-addressed, point-in-time capture of
  the traffic configuration a session runs against (closes the ADR-021 gap).
- ProcessingSession: durable session record + bounded progress. State is written
  ONLY through apps.processing.services.state.transition() (single-writer rule).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import UUIDModel, UUIDTimeStampedModel
from apps.governance.models import AIModelVersion
from apps.ingestion.models import VideoAsset
from apps.network.models import Camera
from apps.processing.states import (
    NON_TERMINAL_STATES,
    ProcessingState,
    RequestedAction,
)


class ProcessingConfigSnapshot(UUIDModel):
    """Immutable, deterministic, content-addressed configuration snapshot.

    Deduplicated by `snapshot_hash`: two sessions over identical config reuse one
    row. Immutable after creation (save-guard blocks post-create field writes).
    """

    snapshot_schema_version = models.PositiveIntegerField(default=1)
    payload = models.JSONField()  # canonical, bounded; see services.snapshot
    snapshot_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "processing_config_snapshot"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"snapshot {self.snapshot_hash[:12]} v{self.snapshot_schema_version}"

    def save(self, *args, **kwargs):
        # Immutable: allow the initial insert only. Any later save is a bug.
        if not self._state.adding:
            raise ValueError("ProcessingConfigSnapshot is immutable and cannot be updated")
        super().save(*args, **kwargs)


class ProcessingSession(UUIDTimeStampedModel):
    # --- Identity / binding (set once at creation) ---
    video_asset = models.ForeignKey(
        VideoAsset, on_delete=models.PROTECT, related_name="processing_sessions"
    )
    camera = models.ForeignKey(
        Camera, on_delete=models.PROTECT, null=True, blank=True,
        related_name="processing_sessions",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    config_snapshot = models.ForeignKey(
        ProcessingConfigSnapshot, on_delete=models.PROTECT, related_name="sessions"
    )
    processing_params = models.JSONField()  # immutable execution params (§9)

    # --- Lifecycle ---
    state = models.CharField(
        max_length=16, choices=ProcessingState.choices,
        default=ProcessingState.CREATED, db_index=True,
    )
    requested_action = models.CharField(
        max_length=8, choices=RequestedAction.choices, default=RequestedAction.NONE,
    )

    # --- Retry lineage (§24) ---
    retry_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries"
    )
    retry_count = models.PositiveIntegerField(default=0)

    # --- Runtime identity (written by CV runtime) ---
    runtime_id = models.CharField(max_length=64, blank=True, default="")
    runtime_version = models.CharField(max_length=32, blank=True, default="")
    device = models.CharField(max_length=32, blank=True, default="")  # e.g. "cpu"/"cuda:0"

    # --- Error (sanitized) ---
    error_code = models.CharField(max_length=48, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")

    # --- Bounded progress (single-row, throttled writes; never per-frame) ---
    frames_total_estimate = models.BigIntegerField(null=True, blank=True)
    frames_decoded = models.BigIntegerField(default=0)
    frames_processed = models.BigIntegerField(default=0)
    current_frame_index = models.BigIntegerField(null=True, blank=True)
    current_pts_seconds = models.FloatField(null=True, blank=True)
    progress_percent = models.FloatField(null=True, blank=True)
    decode_fps = models.FloatField(null=True, blank=True)
    processing_fps = models.FloatField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)

    # --- Lifecycle timestamps (one per meaningful transition) ---
    queued_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "processing_session"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(state__in=[s for s, _ in ProcessingState.choices]),
                name="ck_processing_session_state_enum",
            ),
            # At most one non-terminal session per video (duplicate-active guard, §30).
            models.UniqueConstraint(
                fields=["video_asset"],
                condition=models.Q(state__in=sorted(NON_TERMINAL_STATES)),
                name="uq_processing_active_per_video",
            ),
        ]
        indexes = [
            models.Index(fields=["state", "last_heartbeat_at"]),
            models.Index(fields=["video_asset", "state"]),
            models.Index(fields=["camera", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"session {self.id} [{self.state}]"

    @property
    def is_terminal(self) -> bool:
        from apps.processing.states import is_terminal
        return is_terminal(self.state)


class FrameDetectionBatch(UUIDModel):
    """Durable per-processed-frame detection record (Phase 6 / §24, D10).

    One row per processed frame; detections are a bounded JSONB list (normalized
    XYXY + canonical class + confidence). Framework-independent. Traceable to
    session/video/frame/timestamp and the producing provider/model identity.
    `is_test_provider=True` marks deterministic TEST output — NOT real AI.
    """

    session = models.ForeignKey(
        ProcessingSession, on_delete=models.PROTECT, related_name="detection_batches"
    )
    video = models.ForeignKey(VideoAsset, on_delete=models.PROTECT, related_name="+")
    model_version = models.ForeignKey(
        AIModelVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    provider_name = models.CharField(max_length=64)
    provider_version = models.CharField(max_length=32, blank=True, default="")
    is_test_provider = models.BooleanField(default=False)
    taxonomy_version = models.CharField(max_length=16)
    source_frame_index = models.BigIntegerField()
    pts_seconds = models.FloatField(null=True, blank=True)
    detection_count = models.PositiveIntegerField(default=0)
    detections = models.JSONField(default=list)  # list[Detection.to_dict()]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "processing_frame_detection_batch"
        ordering = ["session", "source_frame_index"]
        indexes = [
            models.Index(fields=["session", "source_frame_index"]),
            models.Index(fields=["video", "source_frame_index"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "source_frame_index"],
                name="uq_detection_batch_session_frame",
            )
        ]

    def __str__(self) -> str:
        return f"detbatch s={self.session_id} f={self.source_frame_index} n={self.detection_count}"

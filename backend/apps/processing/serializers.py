"""Processing API serializers (Phase 5 §30). Read-only projections; state is never
settable via the API (only the command endpoints set requested_action)."""
from __future__ import annotations

from rest_framework import serializers

from apps.processing.models import (
    FrameDetectionBatch,
    ProcessingConfigSnapshot,
    ProcessingSession,
)


class ProcessingSessionSerializer(serializers.ModelSerializer):
    snapshot_hash = serializers.CharField(source="config_snapshot.snapshot_hash", read_only=True)
    video_id = serializers.UUIDField(source="video_asset_id", read_only=True)
    camera_id = serializers.UUIDField(read_only=True)
    retry_of = serializers.UUIDField(source="retry_of_id", read_only=True)

    class Meta:
        model = ProcessingSession
        fields = [
            "id", "video_id", "camera_id", "state", "requested_action",
            "processing_params", "snapshot_hash",
            "frames_total_estimate", "frames_decoded", "frames_processed",
            "current_frame_index", "current_pts_seconds", "progress_percent",
            "decode_fps", "processing_fps",
            "runtime_id", "runtime_version", "device",
            "error_code", "error_message",
            "retry_of", "retry_count",
            "queued_at", "started_at", "paused_at", "completed_at",
            "failed_at", "cancelled_at", "stopped_at", "cancel_requested_at",
            "last_heartbeat_at", "created_at", "updated_at",
        ]
        read_only_fields = fields


class SnapshotMetadataSerializer(serializers.ModelSerializer):
    """Bounded snapshot metadata — hashes/revisions/counts, NOT a raw geometry dump."""

    camera = serializers.SerializerMethodField()
    counts = serializers.SerializerMethodField()

    class Meta:
        model = ProcessingConfigSnapshot
        fields = ["id", "snapshot_hash", "snapshot_schema_version", "created_at",
                  "camera", "counts"]

    def get_camera(self, obj):
        return (obj.payload or {}).get("camera")

    def get_counts(self, obj):
        p = obj.payload or {}
        return {k: len(p.get(k, [])) for k in
                ("lanes", "rois", "counting_lines", "stop_lines", "camera_lane_coverage")}


class DetectionBatchSerializer(serializers.ModelSerializer):
    """One processed frame's detections + producing-provider identity (Phase 6).

    `is_test_provider=True` marks deterministic TEST output — NOT real AI detection;
    the frontend surfaces a prominent banner from this flag."""

    session_id = serializers.UUIDField(read_only=True)
    model_version_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = FrameDetectionBatch
        fields = [
            "id", "session_id", "source_frame_index", "pts_seconds",
            "provider_name", "provider_version", "is_test_provider",
            "model_version_id", "taxonomy_version",
            "detection_count", "detections", "created_at",
        ]
        read_only_fields = fields


class CreateSessionSerializer(serializers.Serializer):
    video_id = serializers.UUIDField()
    sampling = serializers.DictField(required=False)
    processor = serializers.CharField(required=False)
    device_preference = serializers.CharField(required=False)
    detector = serializers.DictField(required=False)

    def to_params(self) -> dict:
        d = self.validated_data
        params = {}
        if "sampling" in d:
            params["sampling"] = d["sampling"]
        if "processor" in d:
            params["processor"] = d["processor"]
        if "device_preference" in d:
            params["device_preference"] = d["device_preference"]
        if "detector" in d:
            params["detector"] = d["detector"]
        return params

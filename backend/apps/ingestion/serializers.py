"""VideoAsset serializer (read/metadata). No raw filesystem paths exposed."""
from __future__ import annotations

from rest_framework import serializers

from apps.ingestion.models import VideoAsset


class VideoAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoAsset
        fields = [
            "id", "original_filename", "camera", "source_type",
            "size_bytes", "checksum_sha256", "mime_detected",
            "container_format", "codec", "duration_s", "width", "height", "fps", "frame_count",
            "validation_status", "is_active", "error_code", "error_message",
            "has_thumbnail", "privacy_status",
            "recording_started_at", "recording_time_source",
            "uploaded_by", "uploaded_at", "created_at", "updated_at",
        ]
        read_only_fields = fields  # writes go through the ingestion service, not the serializer
        # NOTE: storage_key / stored_artifact / thumbnail_artifact paths are deliberately NOT exposed.


class VideoMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoAsset
        fields = [
            "id", "container_format", "codec", "duration_s", "width", "height",
            "fps", "frame_count", "validation_status",
        ]
        read_only_fields = fields

"""
Stable, extensible data-classification vocabulary (Phase 2 §21 / ADR-015).

Used by retention policies, handlers, and storage governance. The vocabulary is
intentionally broader than the tables that exist today — a category listed here
does NOT imply a table exists. Retention handlers are registered only for
categories with real data.
"""
from __future__ import annotations

from django.db import models


class DataCategory(models.TextChoices):
    SECURITY_AUDIT = "security_audit", "Security audit events"
    SYSTEM_METRIC = "system_metric", "Operational system metrics"
    RAW_VIDEO = "raw_video", "Raw uploaded video"
    EVIDENCE_MEDIA = "evidence_media", "Evidence snapshots/clips"
    DETECTION_METADATA = "detection_metadata", "Raw detection metadata"
    TRACK_METADATA = "track_metadata", "Track-level metadata"
    TRAFFIC_MEASUREMENT = "traffic_measurement", "Traffic measurements"
    AGGREGATED_ANALYTICS = "aggregated_analytics", "Aggregated analytics"
    MODEL_ARTIFACT = "model_artifact", "AI model artifacts"
    SIMULATION_ARTIFACT = "simulation_artifact", "Simulation artifacts"
    EXPORT = "export", "Generated exports"
    # Phase 3 — long-lived reference configuration. Classification only; NOT
    # registered for automatic retention (archived config remains available).
    TRAFFIC_CONFIG = "traffic_config", "Traffic network configuration"
    # Phase 4 — video ingestion.
    VIDEO_THUMBNAIL = "video_thumbnail", "Video thumbnail image"
    # Phase 6T-A — training-data governance. Classification only; large media/manifests
    # live behind StorageBackend/StoredArtifact, never as blobs in PostgreSQL.
    TRAINING_DATA = "training_data", "Training dataset media"
    DATASET_MANIFEST = "dataset_manifest", "Immutable dataset/split manifest"


# Categories with real, retention-manageable data in Phase 2.
PHASE2_ACTIVE_CATEGORIES = frozenset(
    {DataCategory.SECURITY_AUDIT, DataCategory.SYSTEM_METRIC}
)

# Safety floors (days) below which a retention policy for a category may not be
# configured, guarding against accidental aggressive purging of sensitive data.
RETENTION_FLOOR_DAYS: dict[str, int] = {
    DataCategory.SECURITY_AUDIT: 30,
}

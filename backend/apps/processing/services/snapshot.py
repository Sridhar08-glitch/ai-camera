"""
Immutable configuration snapshot capture (Phase 5 / ADR-026).

Captures exactly what future CV processing needs — camera, covered lanes, ROIs,
counting lines, stop lines (each with revision+config_hash+geometry via the
existing versioned_payload) plus the video decode-identity facts. Canonical,
deterministic, bounded, hashable. Deduplicated by content hash.

Excludes secrets, audit, user PII, and unrelated topology.
"""
from __future__ import annotations

from typing import Any

from apps.common.versioning import canonical_hash
from apps.processing.models import ProcessingConfigSnapshot

SNAPSHOT_SCHEMA_VERSION = 1


def build_payload(video_asset) -> dict[str, Any]:
    """Build the canonical snapshot payload for a VideoAsset's camera config.

    Deterministic: entities are ordered by id; geometry is taken verbatim from
    each entity's frozen versioned_payload().
    """
    camera = video_asset.camera
    payload: dict[str, Any] = {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "coordinate_spaces": ["image_normalized"],
        "video": {
            "video_asset_id": str(video_asset.id),
            "checksum_sha256": video_asset.checksum_sha256,
            "fps": video_asset.fps,
            "duration_s": video_asset.duration_s,
            "width": video_asset.width,
            "height": video_asset.height,
            "frame_count": video_asset.frame_count,
        },
        "camera": None,
        "camera_lane_coverage": [],
        "lanes": [],
        "rois": [],
        "counting_lines": [],
        "stop_lines": [],
    }

    if camera is None:
        # A session may run against a camera-less video (infra validation); the
        # snapshot still binds video identity. No geometry to capture.
        return payload

    payload["camera"] = {
        "id": str(camera.id),
        "revision": camera.revision,
        "config_hash": camera.config_hash,
    }

    coverages = list(camera.coverages.filter(is_active=True).select_related("lane").order_by("lane_id"))
    lane_ids = []
    for cov in coverages:
        payload["camera_lane_coverage"].append({
            "lane_id": str(cov.lane_id),
            "coverage_type": cov.coverage_type,
            "priority": cov.priority,
        })
        lane_ids.append(cov.lane_id)

    seen_lanes = set()
    for cov in coverages:
        lane = cov.lane
        if lane is None or lane.id in seen_lanes:
            continue
        seen_lanes.add(lane.id)
        payload["lanes"].append({
            "id": str(lane.id),
            "revision": lane.revision,
            "config_hash": lane.config_hash,
            **lane.versioned_payload(),
        })
    payload["lanes"].sort(key=lambda d: d["id"])

    for roi in camera.rois.filter(is_active=True).order_by("id"):
        payload["rois"].append({
            "id": str(roi.id), "revision": roi.revision, "config_hash": roi.config_hash,
            **roi.versioned_payload(),
        })
    for cl in camera.counting_lines.filter(is_active=True).order_by("id"):
        payload["counting_lines"].append({
            "id": str(cl.id), "revision": cl.revision, "config_hash": cl.config_hash,
            **cl.versioned_payload(),
        })
    for sl in camera.stop_lines.filter(is_active=True).order_by("id"):
        payload["stop_lines"].append({
            "id": str(sl.id), "revision": sl.revision, "config_hash": sl.config_hash,
            **sl.versioned_payload(),
        })

    return payload


def capture_snapshot(video_asset) -> ProcessingConfigSnapshot:
    """Build + persist (or reuse) the immutable snapshot for a video's config.

    Content-hash deduplicated: identical config → the existing snapshot row.
    """
    payload = build_payload(video_asset)
    digest = canonical_hash(payload)
    existing = ProcessingConfigSnapshot.objects.filter(snapshot_hash=digest).first()
    if existing is not None:
        return existing
    return ProcessingConfigSnapshot.objects.create(
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        payload=payload,
        snapshot_hash=digest,
    )

"""Helpers for Phase 5 processing tests: build a VALID VideoAsset backed by a real
decodable file in the (temp) storage backend, plus network config for snapshots."""
from __future__ import annotations

import hashlib
from pathlib import Path

from apps.common.datacategories import DataCategory
from apps.governance.models import ArtifactState, StoredArtifact
from apps.ingestion.models import ValidationStatus, VideoAsset
from apps.ingestion.storage import content_key, get_storage_backend
from tests._video_fixtures import make_test_video_bytes


def make_valid_video(*, w=64, h=48, fps=6, seconds=1.0, camera=None, content=None) -> VideoAsset:
    raw = content if content is not None else make_test_video_bytes(w=w, h=h, fps=fps, seconds=seconds)
    checksum = hashlib.sha256(raw).hexdigest()
    key = content_key(checksum, "mp4")
    backend = get_storage_backend()
    path = Path(backend.resolve_path(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    artifact = StoredArtifact.objects.create(
        category=DataCategory.RAW_VIDEO, path=key, checksum_sha256=checksum,
        size_bytes=len(raw), state=ArtifactState.PRESENT,
    )
    return VideoAsset.objects.create(
        original_filename="fixture.mp4", storage_key=key, stored_artifact=artifact,
        camera=camera, size_bytes=len(raw), checksum_sha256=checksum,
        validation_status=ValidationStatus.VALID, is_active=True,
        container_format="mp4", codec="mpeg4", duration_s=seconds,
        width=w, height=h, fps=float(fps), frame_count=int(round(fps * seconds)),
    )


def make_camera_with_config():
    """Create a Camera with a lane, ROI, counting line, and stop line for snapshots."""
    from apps.network.models import (
        Camera, CameraLaneCoverage, City, CountingLine, Lane, RegionOfInterest,
        Road, RoadSegment, StopLine,
    )
    from apps.network.models import enums

    city = City.objects.create(name="Testville", code="TV")
    road = Road.objects.create(city=city, name="Main", code="MN",
                               road_type=enums.RoadType.PRIMARY,
                               directionality=enums.Directionality.TWO_WAY)
    seg = RoadSegment.objects.create(road=road, direction=enums.SegmentDirection.FORWARD)
    lane = Lane.objects.create(road_segment=seg, lane_index=1,
                               direction=enums.LaneDirection.FORWARD,
                               lane_type=enums.LaneType.GENERAL)
    cam = Camera.objects.create(city=city, name="Cam1", code="C1",
                                camera_type=enums.CameraType.FIXED,
                                source_type=enums.SourceType.UPLOADED)
    CameraLaneCoverage.objects.create(camera=cam, lane=lane,
                                      coverage_type=enums.CoverageType.PRIMARY)
    RegionOfInterest.objects.create(
        camera=cam, name="roi1", roi_type=enums.ROIType.DETECTION,
        polygon={"space": "image_normalized", "coordinates": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]},
        lane=lane,
    )
    CountingLine.objects.create(
        camera=cam, lane=lane, name="cl1",
        start={"x": 0.1, "y": 0.5}, end={"x": 0.9, "y": 0.5},
        counting_direction=enums.CountingDirection.AB,
    )
    StopLine.objects.create(
        camera=cam, lane=lane, name="sl1",
        line={"space": "image_normalized", "coordinates": [[0.2, 0.6], [0.8, 0.6]]},
    )
    return cam, lane

"""Image-space configuration (Phase 3): ROI, CountingLine, StopLine. Normalized 0..1."""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.network.models.base import VersionedConfigMixin
from apps.network.models import enums
from apps.network.models.camera import Camera
from apps.network.models.topology import Approach, Lane


class RegionOfInterest(VersionedConfigMixin, UUIDTimeStampedModel):
    camera = models.ForeignKey(Camera, on_delete=models.PROTECT, related_name="rois")
    name = models.CharField(max_length=128)
    roi_type = models.CharField(max_length=16, choices=enums.ROIType.choices, default=enums.ROIType.DETECTION)
    polygon = models.JSONField()  # {"space":"image_normalized","coordinates":[[x,y],...]}
    lane = models.ForeignKey(Lane, on_delete=models.SET_NULL, null=True, blank=True, related_name="rois")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_region_of_interest"
        ordering = ["camera", "name"]
        constraints = [
            models.UniqueConstraint(fields=["camera", "name"], name="uq_roi_camera_name")
        ]
        indexes = [models.Index(fields=["camera", "is_active"])]

    def versioned_payload(self) -> dict:
        return {
            "camera_id": str(self.camera_id),
            "roi_type": self.roi_type,
            "polygon": self.polygon,
            "lane_id": str(self.lane_id) if self.lane_id else None,
        }


class CountingLine(VersionedConfigMixin, UUIDTimeStampedModel):
    camera = models.ForeignKey(Camera, on_delete=models.PROTECT, related_name="counting_lines")
    lane = models.ForeignKey(Lane, on_delete=models.SET_NULL, null=True, blank=True, related_name="counting_lines")
    name = models.CharField(max_length=128)
    start = models.JSONField()  # {"x":..,"y":..} normalized
    end = models.JSONField()    # {"x":..,"y":..} normalized
    counting_direction = models.CharField(max_length=8, choices=enums.CountingDirection.choices, default=enums.CountingDirection.BOTH)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_counting_line"
        ordering = ["camera", "name"]
        constraints = [
            models.UniqueConstraint(fields=["camera", "name"], name="uq_counting_line_camera_name")
        ]
        indexes = [models.Index(fields=["camera", "is_active"])]

    def versioned_payload(self) -> dict:
        return {
            "camera_id": str(self.camera_id),
            "lane_id": str(self.lane_id) if self.lane_id else None,
            "start": self.start,
            "end": self.end,
            "counting_direction": self.counting_direction,
        }


class StopLine(VersionedConfigMixin, UUIDTimeStampedModel):
    camera = models.ForeignKey(Camera, on_delete=models.PROTECT, related_name="stop_lines")
    approach = models.ForeignKey(Approach, on_delete=models.SET_NULL, null=True, blank=True, related_name="stop_lines")
    lane = models.ForeignKey(Lane, on_delete=models.SET_NULL, null=True, blank=True, related_name="stop_lines")
    name = models.CharField(max_length=128)
    line = models.JSONField()  # {"space":"image_normalized","coordinates":[[x,y],[x,y]]}
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_stop_line"
        ordering = ["camera", "name"]
        constraints = [
            models.UniqueConstraint(fields=["camera", "name"], name="uq_stop_line_camera_name")
        ]
        indexes = [models.Index(fields=["camera", "is_active"])]

    def versioned_payload(self) -> dict:
        return {
            "camera_id": str(self.camera_id),
            "approach_id": str(self.approach_id) if self.approach_id else None,
            "lane_id": str(self.lane_id) if self.lane_id else None,
            "line": self.line,
        }

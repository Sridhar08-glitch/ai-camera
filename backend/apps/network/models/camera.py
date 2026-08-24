"""Camera asset + camera→lane coverage (Phase 3). Configuration only — NO creds."""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.network.models.base import VersionedConfigMixin
from apps.network.models import enums
from apps.network.models.topology import City, Intersection, Lane, Zone


class Camera(VersionedConfigMixin, UUIDTimeStampedModel):
    """Logical/physical camera asset metadata. NO credentials, URLs, or streams."""

    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="cameras")
    intersection = models.ForeignKey(Intersection, on_delete=models.SET_NULL, null=True, blank=True, related_name="cameras")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="cameras")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    bearing_deg = models.PositiveSmallIntegerField(null=True, blank=True)
    camera_type = models.CharField(max_length=16, choices=enums.CameraType.choices, default=enums.CameraType.FIXED)
    source_type = models.CharField(max_length=16, choices=enums.SourceType.choices, default=enums.SourceType.UNCONFIGURED)
    install_metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    lanes = models.ManyToManyField(Lane, through="network.CameraLaneCoverage", related_name="cameras")

    class Meta:
        db_table = "network_camera"
        ordering = ["city", "code"]
        constraints = [
            models.UniqueConstraint(fields=["city", "code"], name="uq_camera_city_code")
        ]
        indexes = [
            models.Index(fields=["city", "is_active"]),
            models.Index(fields=["intersection"]),
            models.Index(fields=["zone"]),
        ]

    def versioned_payload(self) -> dict:
        return {
            "city_id": str(self.city_id),
            "intersection_id": str(self.intersection_id) if self.intersection_id else None,
            "zone_id": str(self.zone_id) if self.zone_id else None,
            "location_lat": str(self.location_lat) if self.location_lat is not None else None,
            "location_lng": str(self.location_lng) if self.location_lng is not None else None,
            "bearing_deg": self.bearing_deg,
            "camera_type": self.camera_type,
            "source_type": self.source_type,
        }


class CameraLaneCoverage(UUIDTimeStampedModel):
    """Explicit M:N — one camera observes many lanes, one lane seen by many cameras."""

    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="coverages")
    lane = models.ForeignKey(Lane, on_delete=models.CASCADE, related_name="coverages")
    coverage_type = models.CharField(max_length=16, choices=enums.CoverageType.choices, default=enums.CoverageType.PRIMARY)
    priority = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_camera_lane_coverage"
        ordering = ["camera", "priority"]
        constraints = [
            models.UniqueConstraint(fields=["camera", "lane"], name="uq_coverage_camera_lane")
        ]
        indexes = [models.Index(fields=["camera"]), models.Index(fields=["lane"])]

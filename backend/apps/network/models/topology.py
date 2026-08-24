"""Traffic network topology models (Phase 3): City → … → Lane."""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDTimeStampedModel
from apps.network.models.base import VersionedConfigMixin
from apps.network.models import enums


class City(UUIDTimeStampedModel):
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32, unique=True)
    country_code = models.CharField(max_length=2, blank=True, default="")
    timezone = models.CharField(max_length=64, blank=True, default="UTC")
    center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    boundary = models.JSONField(null=True, blank=True)  # geo polygon (GeoJSON order)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "network_city"
        ordering = ["code"]
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self) -> str:
        return self.code


class Zone(UUIDTimeStampedModel):
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="zones")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    boundary = models.JSONField(null=True, blank=True)  # zones MAY overlap (no partition)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_zone"
        ordering = ["city", "code"]
        constraints = [
            models.UniqueConstraint(fields=["city", "code"], name="uq_zone_city_code")
        ]
        indexes = [models.Index(fields=["city", "is_active"])]

    def __str__(self) -> str:
        return f"{self.city.code}/{self.code}"


class Road(UUIDTimeStampedModel):
    # A road belongs to a City; it may cross multiple zones (zone is at segment level).
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="roads")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    road_type = models.CharField(max_length=16, choices=enums.RoadType.choices, default=enums.RoadType.OTHER)
    directionality = models.CharField(max_length=8, choices=enums.Directionality.choices, default=enums.Directionality.TWO_WAY)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_road"
        ordering = ["city", "code"]
        constraints = [
            models.UniqueConstraint(fields=["city", "code"], name="uq_road_city_code")
        ]
        indexes = [models.Index(fields=["city", "is_active"])]

    def __str__(self) -> str:
        return f"{self.city.code}/{self.code}"


class RoadSegment(UUIDTimeStampedModel):
    road = models.ForeignKey(Road, on_delete=models.PROTECT, related_name="segments")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="segments")
    start_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    start_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    end_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    end_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    geometry = models.JSONField(null=True, blank=True)  # geo polyline (GeoJSON order)
    length_m = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    length_source = models.CharField(max_length=8, choices=enums.LengthSource.choices, default=enums.LengthSource.MANUAL)
    direction = models.CharField(max_length=8, choices=enums.SegmentDirection.choices, default=enums.SegmentDirection.BOTH)
    speed_limit_kph = models.PositiveIntegerField(null=True, blank=True)
    lane_count = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_road_segment"
        ordering = ["road"]
        indexes = [models.Index(fields=["road", "is_active"]), models.Index(fields=["zone"])]


class Intersection(UUIDTimeStampedModel):
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="intersections")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name="intersections")
    name = models.CharField(max_length=128)
    code = models.CharField(max_length=32)
    location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    intersection_type = models.CharField(max_length=16, choices=enums.IntersectionType.choices, default=enums.IntersectionType.JUNCTION)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_intersection"
        ordering = ["city", "code"]
        constraints = [
            models.UniqueConstraint(fields=["city", "code"], name="uq_intersection_city_code")
        ]
        indexes = [models.Index(fields=["city", "is_active"]), models.Index(fields=["zone"])]


class Approach(UUIDTimeStampedModel):
    intersection = models.ForeignKey(Intersection, on_delete=models.PROTECT, related_name="approaches")
    road_segment = models.ForeignKey(RoadSegment, on_delete=models.PROTECT, related_name="approaches")
    direction = models.CharField(max_length=2, choices=enums.CardinalDirection.choices, blank=True, default="")
    bearing_deg = models.PositiveSmallIntegerField(null=True, blank=True)  # 0..359
    approach_type = models.CharField(max_length=16, choices=enums.ApproachType.choices, default=enums.ApproachType.INCOMING)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_approach"
        ordering = ["intersection"]
        indexes = [models.Index(fields=["intersection"]), models.Index(fields=["road_segment"])]


class Lane(VersionedConfigMixin, UUIDTimeStampedModel):
    road_segment = models.ForeignKey(RoadSegment, on_delete=models.PROTECT, related_name="lanes")
    approach = models.ForeignKey(Approach, on_delete=models.SET_NULL, null=True, blank=True, related_name="lanes")
    lane_index = models.PositiveSmallIntegerField()
    direction = models.CharField(max_length=8, choices=enums.LaneDirection.choices, default=enums.LaneDirection.FORWARD)
    lane_type = models.CharField(max_length=16, choices=enums.LaneType.choices, default=enums.LaneType.GENERAL)
    geometry = models.JSONField(null=True, blank=True)  # geo polyline
    width_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    speed_limit_override_kph = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "network_lane"
        ordering = ["road_segment", "lane_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["road_segment", "lane_index", "direction"],
                name="uq_lane_segment_index_direction",
            )
        ]
        indexes = [models.Index(fields=["road_segment", "is_active"]), models.Index(fields=["approach"])]

    def versioned_payload(self) -> dict:
        return {
            "road_segment_id": str(self.road_segment_id),
            "approach_id": str(self.approach_id) if self.approach_id else None,
            "lane_index": self.lane_index,
            "direction": self.direction,
            "lane_type": self.lane_type,
            "geometry": self.geometry,
            "width_m": str(self.width_m) if self.width_m is not None else None,
            "speed_limit_override_kph": self.speed_limit_override_kph,
        }

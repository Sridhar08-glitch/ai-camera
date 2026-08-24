"""Network serializers with geometry + metadata validation (Phase 3)."""
from __future__ import annotations

import json

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.common.coordinatespace import CoordinateSpace
from apps.common import geometry as geo
from apps.network.models import (
    Approach,
    Camera,
    CameraLaneCoverage,
    City,
    CountingLine,
    Intersection,
    Lane,
    RegionOfInterest,
    Road,
    RoadSegment,
    StopLine,
    Zone,
)

VERSION_FIELDS = ["revision", "config_hash"]


def _validate_metadata(value):
    if value in (None, ""):
        return value
    size = len(json.dumps(value, default=str).encode("utf-8"))
    if size > settings.NETWORK_METADATA_MAX_BYTES:
        raise serializers.ValidationError(
            f"metadata too large ({size} > {settings.NETWORK_METADATA_MAX_BYTES} bytes)"
        )
    return value


def _run(validator, *args, **kwargs):
    try:
        validator(*args, **kwargs)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


def _validate_lat(v):
    if v is not None:
        _run(geo.validate_lat, float(v))
    return v


def _validate_lng(v):
    if v is not None:
        _run(geo.validate_lng, float(v))
    return v


def _validate_bearing(v):
    if v is not None:
        _run(geo.validate_bearing, int(v))
    return v


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name", "code", "country_code", "timezone", "center_lat",
                  "center_lng", "boundary", "is_active", "metadata", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_center_lat(self, v): return _validate_lat(v)
    def validate_center_lng(self, v): return _validate_lng(v)
    def validate_metadata(self, v): return _validate_metadata(v)

    def validate_boundary(self, v):
        if v is not None:
            _run(geo.validate_geometry, v, expected_space=CoordinateSpace.GEO, kind="polygon")
        return v


class ZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Zone
        fields = ["id", "city", "name", "code", "boundary", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_boundary(self, v):
        if v is not None:
            _run(geo.validate_geometry, v, expected_space=CoordinateSpace.GEO, kind="polygon")
        return v


class RoadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Road
        fields = ["id", "city", "name", "code", "road_type", "directionality", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoadSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoadSegment
        fields = ["id", "road", "zone", "start_lat", "start_lng", "end_lat", "end_lng",
                  "geometry", "length_m", "length_source", "direction", "speed_limit_kph",
                  "lane_count", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_start_lat(self, v): return _validate_lat(v)
    def validate_start_lng(self, v): return _validate_lng(v)
    def validate_end_lat(self, v): return _validate_lat(v)
    def validate_end_lng(self, v): return _validate_lng(v)

    def validate_geometry(self, v):
        if v is not None:
            _run(geo.validate_geometry, v, expected_space=CoordinateSpace.GEO, kind="polyline")
        return v

    def validate(self, attrs):
        # Zone (if set) must belong to the same city as the road.
        road = attrs.get("road") or getattr(self.instance, "road", None)
        zone = attrs.get("zone") or getattr(self.instance, "zone", None)
        if road and zone and zone.city_id != road.city_id:
            raise serializers.ValidationError({"zone": "Zone must belong to the road's city."})
        return attrs


class IntersectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intersection
        fields = ["id", "city", "zone", "name", "code", "location_lat", "location_lng",
                  "intersection_type", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_location_lat(self, v): return _validate_lat(v)
    def validate_location_lng(self, v): return _validate_lng(v)

    def validate(self, attrs):
        city = attrs.get("city") or getattr(self.instance, "city", None)
        zone = attrs.get("zone") or getattr(self.instance, "zone", None)
        if city and zone and zone.city_id != city.id:
            raise serializers.ValidationError({"zone": "Zone must belong to the same city."})
        return attrs


class ApproachSerializer(serializers.ModelSerializer):
    class Meta:
        model = Approach
        fields = ["id", "intersection", "road_segment", "direction", "bearing_deg",
                  "approach_type", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_bearing_deg(self, v): return _validate_bearing(v)

    def validate(self, attrs):
        # Approach's segment and intersection must be in the same city.
        inter = attrs.get("intersection") or getattr(self.instance, "intersection", None)
        seg = attrs.get("road_segment") or getattr(self.instance, "road_segment", None)
        if inter and seg and seg.road.city_id != inter.city_id:
            raise serializers.ValidationError(
                {"road_segment": "Road segment must belong to the intersection's city."}
            )
        return attrs


class LaneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lane
        fields = ["id", "road_segment", "approach", "lane_index", "direction", "lane_type",
                  "geometry", "width_m", "speed_limit_override_kph", "is_active",
                  "revision", "config_hash", "created_at", "updated_at"]
        read_only_fields = ["id", *VERSION_FIELDS, "created_at", "updated_at"]

    def validate_geometry(self, v):
        if v is not None:
            _run(geo.validate_geometry, v, expected_space=CoordinateSpace.GEO, kind="polyline")
        return v

    def validate(self, attrs):
        seg = attrs.get("road_segment") or getattr(self.instance, "road_segment", None)
        approach = attrs.get("approach") or getattr(self.instance, "approach", None)
        if seg and approach and approach.road_segment_id != seg.id:
            raise serializers.ValidationError(
                {"approach": "Approach must reference the same road segment as the lane."}
            )
        return attrs


class CameraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Camera
        fields = ["id", "city", "intersection", "zone", "name", "code", "location_lat",
                  "location_lng", "bearing_deg", "camera_type", "source_type",
                  "install_metadata", "is_active", "revision", "config_hash",
                  "created_at", "updated_at"]
        read_only_fields = ["id", *VERSION_FIELDS, "created_at", "updated_at"]

    def validate_location_lat(self, v): return _validate_lat(v)
    def validate_location_lng(self, v): return _validate_lng(v)
    def validate_bearing_deg(self, v): return _validate_bearing(v)
    def validate_install_metadata(self, v): return _validate_metadata(v)

    def validate(self, attrs):
        city = attrs.get("city") or getattr(self.instance, "city", None)
        for field in ("intersection", "zone"):
            obj = attrs.get(field) or getattr(self.instance, field, None)
            if city and obj and obj.city_id != city.id:
                raise serializers.ValidationError({field: f"{field} must belong to the same city."})
        return attrs


class CameraLaneCoverageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CameraLaneCoverage
        fields = ["id", "camera", "lane", "coverage_type", "priority", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class _ImageSpaceMixin:
    def _validate_polygon(self, v):
        _run(geo.validate_geometry, v, expected_space=CoordinateSpace.IMAGE_NORMALIZED, kind="polygon")
        return v

    def _validate_line(self, v):
        _run(geo.validate_geometry, v, expected_space=CoordinateSpace.IMAGE_NORMALIZED, kind="line")
        return v

    def _validate_point(self, v):
        _run(geo.validate_point_dict, v, space=CoordinateSpace.IMAGE_NORMALIZED)
        return v


class RegionOfInterestSerializer(_ImageSpaceMixin, serializers.ModelSerializer):
    class Meta:
        model = RegionOfInterest
        fields = ["id", "camera", "name", "roi_type", "polygon", "lane", "is_active",
                  "revision", "config_hash", "created_at", "updated_at"]
        read_only_fields = ["id", *VERSION_FIELDS, "created_at", "updated_at"]

    def validate_polygon(self, v): return self._validate_polygon(v)


class CountingLineSerializer(_ImageSpaceMixin, serializers.ModelSerializer):
    class Meta:
        model = CountingLine
        fields = ["id", "camera", "lane", "name", "start", "end", "counting_direction",
                  "is_active", "revision", "config_hash", "created_at", "updated_at"]
        read_only_fields = ["id", *VERSION_FIELDS, "created_at", "updated_at"]

    def validate_start(self, v): return self._validate_point(v)
    def validate_end(self, v): return self._validate_point(v)

    def validate(self, attrs):
        start = attrs.get("start") or getattr(self.instance, "start", None)
        end = attrs.get("end") or getattr(self.instance, "end", None)
        if start and end and start == end:
            raise serializers.ValidationError("counting line endpoints must differ")
        return attrs


class StopLineSerializer(_ImageSpaceMixin, serializers.ModelSerializer):
    class Meta:
        model = StopLine
        fields = ["id", "camera", "approach", "lane", "name", "line", "is_active",
                  "revision", "config_hash", "created_at", "updated_at"]
        read_only_fields = ["id", *VERSION_FIELDS, "created_at", "updated_at"]

    def validate_line(self, v): return self._validate_line(v)

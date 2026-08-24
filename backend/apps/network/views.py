"""Network API viewsets (Phase 3 §16/§23/§24)."""
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.network.audit_mixin import AuditedModelViewSet, HardDeleteSystemAdminMixin
from apps.network import serializers as s
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


class BaseNetworkViewSet(AuditedModelViewSet, viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_map: dict[str, str] = {}

    def get_queryset(self):
        qs = self.queryset
        for param, field in self.filter_map.items():
            val = self.request.query_params.get(param)
            if val is not None and val != "":
                qs = qs.filter(**{field: val})
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return qs


class CityViewSet(BaseNetworkViewSet):
    queryset = City.objects.all()
    serializer_class = s.CitySerializer
    audit_target = "City"

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        """Nested JSON export of a city's network (Phase 3 §25, D5 export-only)."""
        city = self.get_object()
        data = _export_city(city)
        return Response({"data": data})


class ZoneViewSet(BaseNetworkViewSet):
    queryset = Zone.objects.select_related("city").all()
    serializer_class = s.ZoneSerializer
    audit_target = "Zone"
    filter_map = {"city": "city_id"}


class RoadViewSet(BaseNetworkViewSet):
    queryset = Road.objects.select_related("city").all()
    serializer_class = s.RoadSerializer
    audit_target = "Road"
    filter_map = {"city": "city_id"}


class RoadSegmentViewSet(BaseNetworkViewSet):
    queryset = RoadSegment.objects.select_related("road", "zone").all()
    serializer_class = s.RoadSegmentSerializer
    audit_target = "RoadSegment"
    filter_map = {"road": "road_id", "zone": "zone_id"}


class IntersectionViewSet(BaseNetworkViewSet):
    queryset = Intersection.objects.select_related("city", "zone").all()
    serializer_class = s.IntersectionSerializer
    audit_target = "Intersection"
    filter_map = {"city": "city_id", "zone": "zone_id"}


class ApproachViewSet(BaseNetworkViewSet):
    queryset = Approach.objects.select_related("intersection", "road_segment").all()
    serializer_class = s.ApproachSerializer
    audit_target = "Approach"
    filter_map = {"intersection": "intersection_id", "road_segment": "road_segment_id"}


class LaneViewSet(BaseNetworkViewSet):
    queryset = Lane.objects.select_related("road_segment", "approach").all()
    serializer_class = s.LaneSerializer
    audit_target = "Lane"
    filter_map = {"road_segment": "road_segment_id", "approach": "approach_id"}


class CameraViewSet(BaseNetworkViewSet):
    queryset = Camera.objects.select_related("city", "intersection", "zone").all()
    serializer_class = s.CameraSerializer
    audit_target = "Camera"
    filter_map = {"city": "city_id", "intersection": "intersection_id", "zone": "zone_id"}


class CameraLaneCoverageViewSet(BaseNetworkViewSet):
    queryset = CameraLaneCoverage.objects.select_related("camera", "lane").all()
    serializer_class = s.CameraLaneCoverageSerializer
    audit_target = "CameraLaneCoverage"
    archive_on_delete = False  # relationship: hard delete allowed for admins
    filter_map = {"camera": "camera_id", "lane": "lane_id"}


class RegionOfInterestViewSet(HardDeleteSystemAdminMixin, BaseNetworkViewSet):
    queryset = RegionOfInterest.objects.select_related("camera", "lane").all()
    serializer_class = s.RegionOfInterestSerializer
    audit_target = "RegionOfInterest"
    filter_map = {"camera": "camera_id", "lane": "lane_id"}


class CountingLineViewSet(HardDeleteSystemAdminMixin, BaseNetworkViewSet):
    queryset = CountingLine.objects.select_related("camera", "lane").all()
    serializer_class = s.CountingLineSerializer
    audit_target = "CountingLine"
    filter_map = {"camera": "camera_id", "lane": "lane_id"}


class StopLineViewSet(HardDeleteSystemAdminMixin, BaseNetworkViewSet):
    queryset = StopLine.objects.select_related("camera", "approach", "lane").all()
    serializer_class = s.StopLineSerializer
    audit_target = "StopLine"
    filter_map = {"camera": "camera_id", "approach": "approach_id"}


def _export_city(city: City) -> dict:
    return {
        "city": s.CitySerializer(city).data,
        "zones": s.ZoneSerializer(city.zones.all(), many=True).data,
        "roads": [
            {
                **s.RoadSerializer(road).data,
                "segments": [
                    {
                        **s.RoadSegmentSerializer(seg).data,
                        "lanes": s.LaneSerializer(seg.lanes.all(), many=True).data,
                    }
                    for seg in road.segments.all()
                ],
            }
            for road in city.roads.all()
        ],
        "intersections": [
            {
                **s.IntersectionSerializer(inter).data,
                "approaches": s.ApproachSerializer(inter.approaches.all(), many=True).data,
            }
            for inter in city.intersections.all()
        ],
        "cameras": [
            {
                **s.CameraSerializer(cam).data,
                "coverages": s.CameraLaneCoverageSerializer(cam.coverages.all(), many=True).data,
                "regions_of_interest": s.RegionOfInterestSerializer(cam.rois.all(), many=True).data,
                "counting_lines": s.CountingLineSerializer(cam.counting_lines.all(), many=True).data,
                "stop_lines": s.StopLineSerializer(cam.stop_lines.all(), many=True).data,
            }
            for cam in city.cameras.all()
        ],
    }

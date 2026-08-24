"""Observability API (Phase 2 §23). Visible to system_admin + traffic_admin."""
from __future__ import annotations

from datetime import timedelta

from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from apps.common.permissions import HasAnyRole
from apps.common.roles import RoleCode
from apps.observability.models import SystemMetric
from apps.observability.serializers import SystemMetricSerializer


class _ObservabilityRead(HasAnyRole):
    allowed_roles = frozenset({RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN})


class ObservabilitySummaryView(APIView):
    permission_classes = [_ObservabilityRead]

    def get(self, request):
        since = timezone.now() - timedelta(hours=1)
        recent = SystemMetric.objects.filter(bucket_start__gte=since)
        summary: dict[str, float] = {}
        for name in ("http_requests_total", "http_errors_total"):
            summary[name] = float(
                sum(m.value for m in recent.filter(name=name))
            )
        return Response(
            {
                "window_hours": 1,
                "metric_counts": recent.count(),
                "totals": summary,
            }
        )


class SystemMetricViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [_ObservabilityRead]
    serializer_class = SystemMetricSerializer

    def get_queryset(self):
        qs = SystemMetric.objects.all()
        p = self.request.query_params
        if p.get("name"):
            qs = qs.filter(name=p["name"])
        if p.get("runtime"):
            qs = qs.filter(runtime=p["runtime"])
        if p.get("from"):
            qs = qs.filter(bucket_start__gte=p["from"])
        if p.get("to"):
            qs = qs.filter(bucket_start__lte=p["to"])
        return qs

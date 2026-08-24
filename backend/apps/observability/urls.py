"""Observability routes under /api/v1/observability/."""
from django.urls import path

from apps.observability.views import ObservabilitySummaryView, SystemMetricViewSet

_metrics = SystemMetricViewSet.as_view({"get": "list"})

urlpatterns = [
    path("summary", ObservabilitySummaryView.as_view(), name="observability-summary"),
    path("metrics", _metrics, name="observability-metrics"),
]

"""Health routes mounted at /api/."""
from django.urls import path

from apps.health.views import HealthzView, ReadyzView

urlpatterns = [
    path("healthz", HealthzView.as_view(), name="healthz"),
    path("readyz", ReadyzView.as_view(), name="readyz"),
]

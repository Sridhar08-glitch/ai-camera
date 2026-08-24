"""Audit routes: /api/v1/audit/events (list) and /events/{id} (detail)."""
from django.urls import path

from apps.audit.views import AuditEventViewSet

_list = AuditEventViewSet.as_view({"get": "list"})
_detail = AuditEventViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("events", _list, name="audit-event-list"),
    path("events/<uuid:pk>", _detail, name="audit-event-detail"),
]

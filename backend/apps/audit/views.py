"""Read-only audit API (Phase 2 §23). system_admin only. No write routes."""
from __future__ import annotations

from rest_framework import mixins, viewsets

from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer
from apps.common.permissions import IsSystemAdmin


class AuditEventViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """List/retrieve only — audit records are immutable and never mutated via API."""

    permission_classes = [IsSystemAdmin]
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        p = self.request.query_params
        if p.get("event_type"):
            qs = qs.filter(event_type=p["event_type"])
        if p.get("outcome"):
            qs = qs.filter(outcome=p["outcome"])
        if p.get("actor"):
            qs = qs.filter(actor_id=p["actor"])
        if p.get("target_type"):
            qs = qs.filter(target_type=p["target_type"])
        if p.get("from"):
            qs = qs.filter(created_at__gte=p["from"])
        if p.get("to"):
            qs = qs.filter(created_at__lte=p["to"])
        return qs

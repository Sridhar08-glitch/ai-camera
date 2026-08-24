"""Read-only serializer for audit events."""
from __future__ import annotations

from rest_framework import serializers

from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "event_type",
            "action",
            "outcome",
            "actor_id",
            "actor_email",
            "actor_role",
            "target_type",
            "target_id",
            "request_id",
            "source",
            "ip_address",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

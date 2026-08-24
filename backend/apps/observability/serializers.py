from __future__ import annotations

from rest_framework import serializers

from apps.observability.models import SystemMetric


class SystemMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemMetric
        fields = ["id", "name", "runtime", "component", "value", "unit", "labels", "host", "process", "bucket_start", "created_at"]
        read_only_fields = fields

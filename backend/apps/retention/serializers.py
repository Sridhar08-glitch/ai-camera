"""Retention serializers with safety-floor validation."""
from __future__ import annotations

from rest_framework import serializers

from apps.common.datacategories import RETENTION_FLOOR_DAYS
from apps.retention.models import RetentionPolicy, RetentionRun


class RetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionPolicy
        fields = [
            "id", "category", "retention_days", "enabled", "deletion_strategy",
            "batch_size", "max_deletes_per_run", "dry_run_default", "config",
            "last_run_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "category", "last_run_at", "created_at", "updated_at"]

    def validate_retention_days(self, value: int) -> int:
        category = self.instance.category if self.instance else None
        floor = RETENTION_FLOOR_DAYS.get(category, 1)
        if value < floor:
            raise serializers.ValidationError(
                f"retention_days for {category} may not be below the safety floor of {floor} days."
            )
        return value


class RetentionRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetentionRun
        fields = [
            "id", "policy", "started_at", "finished_at", "dry_run",
            "scanned", "deleted", "outcome", "error", "request_id", "source",
        ]
        read_only_fields = fields

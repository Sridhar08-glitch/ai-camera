"""
SystemMetric — pre-aggregated, sampled operational metric rows (Phase 2 §14 / ADR-017).

Not per-event: a Celery beat task flushes in-memory aggregates into this table.
`labels` is validated against a per-metric allowlist to bound cardinality.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDModel


class SystemMetric(UUIDModel):
    name = models.CharField(max_length=64, db_index=True)
    runtime = models.CharField(max_length=16, default="django")  # django/celery/system
    component = models.CharField(max_length=64, blank=True, default="")
    value = models.FloatField()
    unit = models.CharField(max_length=16, default="count")
    labels = models.JSONField(default=dict, blank=True)
    host = models.CharField(max_length=128, blank=True, default="")
    process = models.CharField(max_length=64, blank=True, default="")
    bucket_start = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "observability_system_metric"
        ordering = ["-bucket_start"]
        indexes = [models.Index(fields=["name", "bucket_start"])]

    def __str__(self) -> str:
        return f"{self.name}={self.value}{self.unit}@{self.bucket_start:%Y-%m-%dT%H:%M}"

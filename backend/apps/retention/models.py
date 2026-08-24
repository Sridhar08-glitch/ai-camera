"""Retention policy + run records (Phase 2 §18–19 / ADR-015)."""
from __future__ import annotations

from django.db import models

from apps.common.datacategories import DataCategory
from apps.common.models import UUIDModel, UUIDTimeStampedModel


class DeletionStrategy(models.TextChoices):
    HARD = "hard", "Hard delete"
    ARCHIVE = "archive", "Archive then delete"


class RetentionPolicy(UUIDTimeStampedModel):
    category = models.CharField(max_length=32, choices=DataCategory.choices, unique=True)
    retention_days = models.PositiveIntegerField()
    enabled = models.BooleanField(default=False)
    deletion_strategy = models.CharField(
        max_length=16, choices=DeletionStrategy.choices, default=DeletionStrategy.HARD
    )
    batch_size = models.PositiveIntegerField(default=1000)
    max_deletes_per_run = models.PositiveIntegerField(default=100000)
    dry_run_default = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "retention_policy"
        ordering = ["category"]

    def __str__(self) -> str:
        return f"{self.category}({self.retention_days}d, enabled={self.enabled})"


class RunOutcome(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    PARTIAL = "partial", "Partial"
    SKIPPED = "skipped", "Skipped"


class RetentionRun(UUIDModel):
    policy = models.ForeignKey(
        RetentionPolicy, on_delete=models.CASCADE, related_name="runs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    dry_run = models.BooleanField(default=True)
    scanned = models.BigIntegerField(default=0)
    deleted = models.BigIntegerField(default=0)
    outcome = models.CharField(max_length=16, choices=RunOutcome.choices, default=RunOutcome.SUCCESS)
    error = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=64, blank=True, default="")
    source = models.CharField(max_length=16, default="celery")

    class Meta:
        db_table = "retention_run"
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["policy", "started_at"])]

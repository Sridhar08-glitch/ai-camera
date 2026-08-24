"""
Foundational abstract models reused by every future domain (Phase 1 §12).

These carry no tables of their own; they are inherited by concrete models.
"""
from __future__ import annotations

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Abstract base giving every row a stable UUID primary key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Abstract base adding created/updated audit timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDTimeStampedModel(UUIDModel, TimeStampedModel):
    """Convenience combination used by most concrete models."""

    class Meta:
        abstract = True

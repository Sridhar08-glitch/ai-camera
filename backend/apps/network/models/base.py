"""Base mixins for network models (Phase 3)."""
from __future__ import annotations

from django.db import models

from apps.common.versioning import canonical_hash


class VersionedConfigMixin(models.Model):
    """
    Adds `revision` + `config_hash` (ADR-021). `revision` starts at 1 and
    increments ONLY when a version-controlled field actually changes (detected by
    comparing the freshly-computed canonical hash to the stored one). Subclasses
    implement `versioned_payload()` returning the dict of version-controlled fields.
    """

    revision = models.PositiveIntegerField(default=1)
    config_hash = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        abstract = True

    def versioned_payload(self) -> dict:  # pragma: no cover - abstract
        raise NotImplementedError

    def save(self, *args, **kwargs):
        new_hash = canonical_hash(self.versioned_payload())
        if self._state.adding:
            self.revision = 1
            self.config_hash = new_hash
        elif new_hash != self.config_hash:
            self.revision = (self.revision or 1) + 1
            self.config_hash = new_hash
        super().save(*args, **kwargs)

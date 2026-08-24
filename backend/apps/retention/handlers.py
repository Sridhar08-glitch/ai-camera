"""
Built-in retention handlers for Phase 2 data categories that actually exist:
SECURITY_AUDIT (audit events) and SYSTEM_METRIC (operational metrics).

Deletion is bounded: it proceeds in batches of `batch_size` and never deletes more
than `max_deletes` rows in a single run. Dry-run returns counts without deleting.
"""
from __future__ import annotations

from apps.common.datacategories import DataCategory
from apps.retention.registry import RetentionHandler, RetentionResult, register


def _bounded_purge(model_manager, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
    qs = model_manager.filter(created_at__lt=cutoff)
    scanned = qs.count()
    if dry_run or scanned == 0:
        return RetentionResult(scanned=scanned, deleted=0)

    deleted = 0
    remaining = min(scanned, max_deletes)
    while remaining > 0:
        take = min(batch_size, remaining)
        ids = list(qs.values_list("pk", flat=True)[:take])
        if not ids:
            break
        n, _ = model_manager.filter(pk__in=ids).delete()
        deleted += n
        remaining -= take
        if n == 0:
            break
    return RetentionResult(scanned=scanned, deleted=deleted)


class AuditRetentionHandler(RetentionHandler):
    category = DataCategory.SECURITY_AUDIT

    def _manager(self):
        # Uses the retention-only manager: the default manager forbids delete, so
        # expiry purge is an explicit, controlled path (ADR-016).
        from apps.audit.models import AuditEvent

        return AuditEvent.retention_objects

    def count(self, cutoff) -> int:
        return self._manager().filter(created_at__lt=cutoff).count()

    def purge(self, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
        return _bounded_purge(
            self._manager(), cutoff, batch_size=batch_size, max_deletes=max_deletes, dry_run=dry_run
        )


class MetricRetentionHandler(RetentionHandler):
    category = DataCategory.SYSTEM_METRIC

    def _manager(self):
        from apps.observability.models import SystemMetric

        return SystemMetric.objects

    def count(self, cutoff) -> int:
        return self._manager().filter(created_at__lt=cutoff).count()

    def purge(self, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
        return _bounded_purge(
            self._manager(), cutoff, batch_size=batch_size, max_deletes=max_deletes, dry_run=dry_run
        )


register(AuditRetentionHandler())
register(MetricRetentionHandler())

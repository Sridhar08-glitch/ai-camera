"""
Retention handler for dataset manifests (Phase 6T-A). DB-only rows referencing
manifest files; bounded + dry-run aware. No policy is seeded by default, so nothing
is purged until an admin configures one.
"""
from __future__ import annotations

from apps.common.datacategories import DataCategory
from apps.retention.registry import RetentionHandler, RetentionResult, register


class DatasetManifestRetentionHandler(RetentionHandler):
    category = DataCategory.DATASET_MANIFEST

    def _qs(self, cutoff):
        from apps.datasets.models import DatasetManifest

        return DatasetManifest.objects.filter(created_at__lt=cutoff)

    def count(self, cutoff) -> int:
        return self._qs(cutoff).count()

    def purge(self, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
        qs = self._qs(cutoff).order_by("created_at")
        scanned = qs.count()
        if dry_run or scanned == 0:
            return RetentionResult(scanned=scanned, deleted=0)
        ids = list(qs.values_list("id", flat=True)[:max_deletes])
        from apps.datasets.models import DatasetManifest

        DatasetManifest.objects.filter(id__in=ids).delete()
        return RetentionResult(scanned=scanned, deleted=len(ids))


register(DatasetManifestRetentionHandler())

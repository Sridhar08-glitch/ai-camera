"""
Retention handler for detection metadata (Phase 6 §38). Purges old
FrameDetectionBatch rows (DB-only; no stored files). Bounded + dry-run aware.
Registered at app-ready. No policy is seeded by default — the engine skips
categories without a policy, so nothing is purged until an admin configures one.
"""
from __future__ import annotations

from apps.common.datacategories import DataCategory
from apps.retention.registry import RetentionHandler, RetentionResult, register


class DetectionMetadataRetentionHandler(RetentionHandler):
    category = DataCategory.DETECTION_METADATA

    def _qs(self, cutoff):
        from apps.processing.models import FrameDetectionBatch

        return FrameDetectionBatch.objects.filter(created_at__lt=cutoff)

    def count(self, cutoff) -> int:
        return self._qs(cutoff).count()

    def purge(self, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
        qs = self._qs(cutoff).order_by("created_at")
        scanned = qs.count()
        if dry_run or scanned == 0:
            return RetentionResult(scanned=scanned, deleted=0)
        ids = list(qs.values_list("id", flat=True)[:max_deletes])
        from apps.processing.models import FrameDetectionBatch

        deleted, _ = FrameDetectionBatch.objects.filter(id__in=ids).delete()
        return RetentionResult(scanned=scanned, deleted=len(ids))


register(DetectionMetadataRetentionHandler())

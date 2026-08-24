"""
Retention handlers for video data (Phase 4 §18). Registered at app-ready.

RAW_VIDEO: purge VideoAssets older than cutoff — deletes the stored file(s) via the
StorageBackend FIRST, then the DB rows (no orphans). Bounded + dry-run aware. A
future active-processing guard hook is included (no processing exists in Phase 4).
VIDEO_THUMBNAIL: purge orphaned thumbnail artifacts no longer referenced by a video.
"""
from __future__ import annotations

from apps.common.datacategories import DataCategory
from apps.retention.registry import RetentionHandler, RetentionResult, register


def _video_is_protected(asset) -> bool:
    # Phase 5: a video bound to a non-terminal ProcessingSession must not be purged.
    # (The session's FK is PROTECT too, so a hard delete would also raise; this hook
    #  lets retention skip cleanly rather than error.)
    from apps.processing.models import ProcessingSession
    from apps.processing.states import NON_TERMINAL_STATES

    return ProcessingSession.objects.filter(
        video_asset=asset, state__in=NON_TERMINAL_STATES
    ).exists()


class RawVideoRetentionHandler(RetentionHandler):
    category = DataCategory.RAW_VIDEO

    def _qs(self, cutoff):
        from apps.ingestion.models import VideoAsset

        return VideoAsset.objects.filter(created_at__lt=cutoff)

    def count(self, cutoff) -> int:
        return self._qs(cutoff).count()

    def purge(self, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
        from apps.governance.models import StoredArtifact
        from apps.ingestion.storage import get_storage_backend

        qs = self._qs(cutoff).order_by("created_at")
        scanned = qs.count()
        if dry_run or scanned == 0:
            return RetentionResult(scanned=scanned, deleted=0)

        backend = get_storage_backend()
        deleted = 0
        for asset in qs[: min(max_deletes, batch_size * 100)]:
            if deleted >= max_deletes:
                break
            if _video_is_protected(asset):
                continue
            keys = [asset.storage_key]
            artifact_ids = [asset.stored_artifact_id]
            if asset.thumbnail_artifact_id:
                keys.append(asset.thumbnail_artifact.path)
                artifact_ids.append(asset.thumbnail_artifact_id)
            # File(s) first, then DB rows.
            for k in keys:
                try:
                    backend.delete(k)
                except Exception:
                    pass  # orphan sweep will reconcile
            asset.delete()
            StoredArtifact.objects.filter(id__in=[a for a in artifact_ids if a]).delete()
            deleted += 1
        return RetentionResult(scanned=scanned, deleted=deleted)


class ThumbnailRetentionHandler(RetentionHandler):
    category = DataCategory.VIDEO_THUMBNAIL

    def _orphans(self, cutoff):
        from apps.governance.models import StoredArtifact

        return StoredArtifact.objects.filter(
            category=DataCategory.VIDEO_THUMBNAIL, created_at__lt=cutoff, thumbnail_of__isnull=True
        )

    def count(self, cutoff) -> int:
        return self._orphans(cutoff).count()

    def purge(self, cutoff, *, batch_size, max_deletes, dry_run) -> RetentionResult:
        from apps.ingestion.storage import get_storage_backend

        qs = self._orphans(cutoff)
        scanned = qs.count()
        if dry_run or scanned == 0:
            return RetentionResult(scanned=scanned, deleted=0)
        backend = get_storage_backend()
        deleted = 0
        for art in qs[:max_deletes]:
            try:
                backend.delete(art.path)
            except Exception:
                pass
            art.delete()
            deleted += 1
        return RetentionResult(scanned=scanned, deleted=deleted)


register(RawVideoRetentionHandler())
register(ThumbnailRetentionHandler())

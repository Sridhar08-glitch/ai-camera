"""Orphan reconciliation (Phase 4 §17). Celery beat cleans temp files + dangling artifacts."""
from __future__ import annotations

import time
from pathlib import Path

from celery import shared_task
from django.conf import settings

from apps.governance.models import ArtifactState, StoredArtifact
from apps.ingestion.storage import get_storage_backend


@shared_task(name="apps.ingestion.tasks.reconcile_storage")
def reconcile_storage() -> dict:
    """Remove stale temp uploads and flag artifacts whose files are missing."""
    backend = get_storage_backend()
    removed_temp = 0
    flagged_missing = 0

    # 1. Stale temp files (interrupted uploads).
    temp_root = Path(settings.VIDEO_TEMP_ROOT)
    if temp_root.exists():
        cutoff = time.time() - settings.VIDEO_TEMP_MAX_AGE_SECONDS
        for f in temp_root.glob("*.upload"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
                    removed_temp += 1
            except OSError:
                pass

    # 2. Present artifacts whose backing file is gone -> flag orphaned (no silent loss).
    for art in StoredArtifact.objects.filter(state=ArtifactState.PRESENT).iterator():
        try:
            if not backend.exists(art.path):
                StoredArtifact.objects.filter(id=art.id).update(state=ArtifactState.ORPHANED)
                flagged_missing += 1
        except Exception:
            pass

    return {"removed_temp": removed_temp, "flagged_missing": flagged_missing}

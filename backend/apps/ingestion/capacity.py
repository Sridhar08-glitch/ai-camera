"""Storage capacity safety (Phase 4 §16): max size, global quota, free-disk reserve."""
from __future__ import annotations

import shutil
from pathlib import Path

from django.conf import settings

from apps.ingestion.storage import get_storage_backend


class CapacityError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def check_upload_allowed(size_bytes: int) -> None:
    """Raise CapacityError if this upload would exceed configured limits."""
    max_bytes = settings.MAX_UPLOAD_BYTES
    if size_bytes <= 0:
        raise CapacityError("empty_file", "file is empty")
    if size_bytes > max_bytes:
        raise CapacityError("file_too_large", f"file exceeds max upload size ({max_bytes} bytes)")

    backend = get_storage_backend()
    usage = backend.total_usage_bytes() if hasattr(backend, "total_usage_bytes") else 0
    quota = settings.VIDEO_STORAGE_QUOTA_BYTES
    if quota and usage + size_bytes > quota:
        raise CapacityError("quota_exceeded", "storage quota exceeded")

    root = Path(settings.VIDEO_STORAGE_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    reserve = settings.MIN_FREE_DISK_BYTES
    if free - size_bytes < reserve:
        raise CapacityError("insufficient_disk_space", "insufficient free disk space")

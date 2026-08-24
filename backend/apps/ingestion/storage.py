"""
Storage backend abstraction (Phase 4 / ADR-022).

Local-first, swappable. Content-addressed, server-generated keys; no client value
participates in the path; no absolute path is ever returned to API clients.
"""
from __future__ import annotations

import hashlib
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from django.conf import settings


class StorageError(Exception):
    pass


def content_key(checksum_sha256: str, ext: str) -> str:
    """Sharded, content-addressed storage key: ab/cd/<sha256>.<ext>."""
    safe_ext = "".join(c for c in (ext or "").lstrip(".").lower() if c.isalnum())[:8]
    c = checksum_sha256.lower()
    tail = f"{c}.{safe_ext}" if safe_ext else c
    return f"{c[:2]}/{c[2:4]}/{tail}"


class StorageBackend(ABC):
    @abstractmethod
    def save(self, src_path: str, key: str) -> int: ...
    @abstractmethod
    def open(self, key: str) -> BinaryIO: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def exists(self, key: str) -> bool: ...
    @abstractmethod
    def size(self, key: str) -> int: ...
    @abstractmethod
    def checksum(self, key: str) -> str: ...
    @abstractmethod
    def resolve_path(self, key: str) -> str:
        """INTERNAL ONLY — never expose the returned path through an API."""


class LocalFileSystemBackend(StorageBackend):
    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.VIDEO_STORAGE_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_path(self, key: str) -> str:
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StorageError("storage key escapes storage root") from exc
        return str(candidate)

    def save(self, src_path: str, key: str) -> int:
        dest = Path(self.resolve_path(key))
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Move (same volume) or copy the already-checksummed temp file into place.
        shutil.move(src_path, dest)
        return dest.stat().st_size

    def open(self, key: str) -> BinaryIO:
        return open(self.resolve_path(key), "rb")

    def delete(self, key: str) -> None:
        p = Path(self.resolve_path(key))
        if p.exists():
            p.unlink()

    def exists(self, key: str) -> bool:
        return Path(self.resolve_path(key)).exists()

    def size(self, key: str) -> int:
        return Path(self.resolve_path(key)).stat().st_size

    def checksum(self, key: str) -> str:
        h = hashlib.sha256()
        with self.open(key) as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def total_usage_bytes(self) -> int:
        total = 0
        for dirpath, _dirs, files in os.walk(self.root):
            for f in files:
                try:
                    total += (Path(dirpath) / f).stat().st_size
                except OSError:
                    pass
        return total


_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    global _backend
    if _backend is None:
        _backend = LocalFileSystemBackend()
    return _backend

"""StorageBackend tests (Phase 4 / ADR-022)."""
from __future__ import annotations

import pytest

from apps.ingestion.storage import (
    LocalFileSystemBackend,
    StorageError,
    content_key,
    get_storage_backend,
)


def test_content_key_is_sharded_and_deterministic():
    k = content_key("a" * 64, "mp4")
    assert k == f"aa/aa/{'a' * 64}.mp4"
    assert content_key("b" * 64, ".MP4") == content_key("b" * 64, "mp4")


def test_save_read_delete_roundtrip(vstorage, tmp_path):
    backend = get_storage_backend()
    src = tmp_path / "src.bin"
    src.write_bytes(b"hello-video")
    key = content_key("c" * 64, "mp4")
    backend.save(str(src), key)
    assert backend.exists(key)
    assert backend.size(key) == len(b"hello-video")
    with backend.open(key) as fh:
        assert fh.read() == b"hello-video"
    backend.delete(key)
    assert not backend.exists(key)


def test_checksum(vstorage, tmp_path):
    import hashlib

    backend = get_storage_backend()
    src = tmp_path / "s.bin"
    data = b"abc123"
    src.write_bytes(data)
    key = content_key("d" * 64, "mp4")
    backend.save(str(src), key)
    assert backend.checksum(key) == hashlib.sha256(data).hexdigest()


def test_traversal_guard(vstorage):
    backend = LocalFileSystemBackend()
    with pytest.raises(StorageError):
        backend.resolve_path("../../etc/passwd")


def test_missing_file_size_raises(vstorage):
    backend = get_storage_backend()
    with pytest.raises(Exception):
        backend.size(content_key("e" * 64, "mp4"))

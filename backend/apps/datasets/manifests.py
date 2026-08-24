"""
Immutable dataset/split manifest serialization + hashing (Phase 6T-A / ADR-035).

A manifest is a deterministic, content-hashed list of per-sample records. The file
on disk is the source of truth for per-sample facts (scales to millions of rows);
the DB stores only its sha256 + counts. Determinism (sorted keys, sorted records)
guarantees identical inputs+config → identical hash → reproducibility + tamper
detection.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Optional

MANIFEST_FORMAT_VERSION = 1


@dataclass
class SampleRecord:
    """One training sample's provenance + eligibility (canonical manifest row)."""

    sample_id: str                 # stable id (e.g. dataset-relative path or synthetic id)
    media_checksum: str            # sha256 of the media file (exact-dedup key)
    source: str = ""               # original source reference
    media_rights: str = ""         # per-sample media-rights note (optional)
    annotation_source: str = ""
    group_key: str = ""            # leakage grouping key (video/camera/scene/sequence/location)
    split: str = ""                # "train" | "val" | "test" | "" (unassigned)
    production_eligible: bool = True
    class_ids: list = field(default_factory=list)  # canonical class ids present

    def to_dict(self) -> dict:
        return asdict(self)


def canonical_bytes(records: list, *, meta: Optional[dict] = None) -> bytes:
    """Deterministic UTF-8 bytes for a manifest: sorted records + sorted keys.

    `meta` (format version, taxonomy, mapping version, seed, grouping) is included in
    the hashed payload so a config change changes the hash."""
    rows = [r.to_dict() if isinstance(r, SampleRecord) else dict(r) for r in records]
    rows.sort(key=lambda d: str(d.get("sample_id", "")))
    payload = {
        "manifest_format_version": MANIFEST_FORMAT_VERSION,
        "meta": meta or {},
        "records": rows,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def manifest_sha256(records: list, *, meta: Optional[dict] = None) -> str:
    return hashlib.sha256(canonical_bytes(records, meta=meta)).hexdigest()


def write_manifest(path: str, records: list, *, meta: Optional[dict] = None) -> str:
    """Write the canonical manifest bytes to `path`; return its sha256."""
    data = canonical_bytes(records, meta=meta)
    with open(path, "wb") as fh:
        fh.write(data)
    return hashlib.sha256(data).hexdigest()


def load_manifest(path: str) -> dict:
    """Read a manifest file → {manifest_format_version, meta, records}. Used by both
    the Django side and the (separate) training package's reader."""
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def verify_manifest_file(path: str, expected_sha256: str) -> bool:
    """Tamper check: recompute the file's sha256 from its canonical records and
    compare. Returns True iff it matches (immutability/integrity guarantee)."""
    doc = load_manifest(path)
    records = doc.get("records", [])
    recomputed = manifest_sha256(records, meta=doc.get("meta"))
    # Also guard against raw-byte tampering that preserves canonical form.
    with open(path, "rb") as fh:
        raw = fh.read()
    raw_sha = hashlib.sha256(raw).hexdigest()
    return recomputed == expected_sha256 and raw_sha == expected_sha256

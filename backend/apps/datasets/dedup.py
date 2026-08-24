"""
Dataset deduplication (Phase 6T-A / plan §24).

Exact duplicate detection via cryptographic content hash (SHA-256) is authoritative.
An optional perceptual near-duplicate hook (aHash over decoded pixels) is provided
but is advisory only — it FLAGS candidates for review and never auto-merges (weak
perceptual similarity must not silently drop distinct images).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_exact_duplicates(items: list) -> dict:
    """`items` = [(sample_id, media_checksum)]. Returns {checksum: [sample_ids]} for
    checksums appearing more than once. Authoritative exact-dedup."""
    by_hash = defaultdict(list)
    for sample_id, checksum in items:
        by_hash[checksum].append(sample_id)
    return {h: ids for h, ids in by_hash.items() if len(ids) > 1}


def dedup_report(items: list) -> dict:
    dupes = find_exact_duplicates(items)
    duplicate_ids = sorted({sid for ids in dupes.values() for sid in ids[1:]})
    return {
        "total": len(items),
        "unique_checksums": len({c for _, c in items}),
        "duplicate_groups": len(dupes),
        "duplicate_sample_ids": duplicate_ids,  # ids beyond the first per group
    }


def ahash_flags(hashes: list, *, max_hamming: int = 4) -> list:
    """Advisory perceptual near-duplicate FLAGS. `hashes` = [(sample_id, ahash_int)].
    Returns candidate pairs within `max_hamming` bits. NEVER auto-removes."""
    flags = []
    n = len(hashes)
    for i in range(n):
        sid_i, hi = hashes[i]
        for j in range(i + 1, n):
            sid_j, hj = hashes[j]
            if bin(hi ^ hj).count("1") <= max_hamming:
                flags.append((sid_i, sid_j))
    return flags

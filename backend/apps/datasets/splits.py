"""
Leakage-safe, deterministic dataset splitting (Phase 6T-A / plan §24, D10, ADR-035).

Mandatory rule: never split adjacent frames of the same sequence/camera/scene into
different train/val/test sets, and never let an exact duplicate cross a split
boundary. We therefore split by *groups*, and additionally union groups that share
a media checksum so identical media can never leak. Deterministic: a seeded RNG +
sorted inputs yield the same split (and manifest hash) every run.
"""
from __future__ import annotations

import random

from apps.datasets.manifests import SampleRecord


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # deterministic root: smaller key wins
            lo, hi = sorted((ra, rb))
            self.parent[hi] = lo


def _effective_groups(records: list) -> dict:
    """Map each sample_id → an effective group id. Start from `group_key` (or the
    sample_id if absent), then union any groups sharing a media checksum so exact
    duplicates land in the same split."""
    uf = _UnionFind()
    by_checksum: dict[str, str] = {}
    base = {}
    for r in records:
        g = r.group_key or f"__sample__:{r.sample_id}"
        base[r.sample_id] = g
        uf.find(g)
        if r.media_checksum:
            if r.media_checksum in by_checksum:
                uf.union(g, by_checksum[r.media_checksum])
            else:
                by_checksum[r.media_checksum] = g
    return {sid: uf.find(g) for sid, g in base.items()}


def assign_splits(
    records: list,
    *,
    seed: int,
    ratios: tuple = (0.8, 0.1, 0.1),
    grouping_strategy: str = "group_key",
) -> list:
    """Return a NEW list of SampleRecords with `.split` set to train|val|test.

    Whole effective-groups are assigned to a single split. Deterministic for a fixed
    seed + input set."""
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError("split ratios must sum to 1.0")
    eff = _effective_groups(records)
    groups = sorted(set(eff.values()))            # deterministic order
    rng = random.Random(seed)
    rng.shuffle(groups)                           # seeded → reproducible

    n = len(groups)
    n_train = int(round(ratios[0] * n))
    n_val = int(round(ratios[1] * n))
    # remainder → test (keeps all groups assigned)
    train_g = set(groups[:n_train])
    val_g = set(groups[n_train:n_train + n_val])
    # test_g = the rest

    def split_for(gid):
        if gid in train_g:
            return "train"
        if gid in val_g:
            return "val"
        return "test"

    out = []
    for r in sorted(records, key=lambda x: x.sample_id):
        out.append(SampleRecord(
            sample_id=r.sample_id, media_checksum=r.media_checksum, source=r.source,
            media_rights=r.media_rights, annotation_source=r.annotation_source,
            group_key=r.group_key, split=split_for(eff[r.sample_id]),
            production_eligible=r.production_eligible, class_ids=list(r.class_ids),
        ))
    return out


def split_counts(records: list) -> dict:
    counts = {"train": 0, "val": 0, "test": 0}
    for r in records:
        if r.split in counts:
            counts[r.split] += 1
    return counts


def check_no_leakage(records: list) -> list:
    """Return a list of leakage violations: any effective-group or media checksum
    that appears in more than one split. Empty list == leakage-free."""
    eff = _effective_groups(records)
    group_splits: dict[str, set] = {}
    checksum_splits: dict[str, set] = {}
    for r in records:
        group_splits.setdefault(eff[r.sample_id], set()).add(r.split)
        if r.media_checksum:
            checksum_splits.setdefault(r.media_checksum, set()).add(r.split)
    violations = []
    for g, splits in group_splits.items():
        if len(splits) > 1:
            violations.append({"type": "group", "key": g, "splits": sorted(splits)})
    for c, splits in checksum_splits.items():
        if len(splits) > 1:
            violations.append({"type": "checksum", "key": c, "splits": sorted(splits)})
    return violations

# ADR-035 — Dataset Manifest & Leakage-Safe Split Strategy

**Status:** Accepted (Phase 6T-A)

## Context
Training reproducibility and integrity require immutable, verifiable per-sample provenance
that scales to millions of samples, and splits that never leak the same sequence/duplicate
across train/val/test.

## Decision
- **Immutable, content-hashed manifests** (`apps.datasets.manifests`): a manifest is a
  deterministic JSON of sorted per-sample records (sample id, media checksum, source,
  group key, split, eligibility, class ids) plus hashed `meta` (format version, taxonomy,
  mapping version, seed, grouping). The **file** is the source of truth for per-sample rows;
  the **DB** (`DatasetManifest`) stores only its **sha256 + counts**. `DatasetManifest` rows
  are immutable (save() raises on update). `verify_manifest_file` recomputes the hash to
  detect tampering.
- **Leakage-safe splitting** (`apps.datasets.splits`): split by **effective groups**, where a
  group starts from `group_key` (video/camera/scene/sequence/location) and is then
  **unioned across any samples sharing a media checksum** — so exact duplicates can never
  cross a split boundary. Assignment is deterministic (seeded RNG over sorted groups).
  `check_no_leakage` asserts no group and no checksum spans multiple splits.
- **Reproducibility:** identical inputs + seed + config → identical split → identical manifest
  hash (test-verified). Recorded on the `DatasetVersion`/`TrainingRun` for full traceability.

## Consequences
A split is reproducible and tamper-evident from its hash alone. Leakage is structurally
prevented, not merely checked after the fact. Large media never enters PostgreSQL.

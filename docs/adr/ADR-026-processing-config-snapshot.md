# ADR-026 — Immutable Processing Configuration Snapshot

**Status:** Accepted (Phase 5)

## Context
ADR-021 documented that `revision` + `config_hash` give change detection but cannot
reconstruct historical configuration, and deferred an immutable snapshot to "before
production CV processing." Phase 5 is the first consumer whose results depend on a
specific traffic configuration, so the snapshot is built now.

## Decision
`ProcessingConfigSnapshot` (UUID PK) — immutable, deterministic, content-addressed:
- **Captured at session creation** (D2), synchronously inside the creation
  transaction, from the video's camera config. A session's `config_snapshot` FK is
  non-null and `PROTECT`.
- **Contents** (bounded): schema version, coordinate spaces, video decode-identity
  (`video_asset_id`, checksum, fps, duration, width, height, frame_count), and for
  the camera — `{id, revision, config_hash}` plus `camera_lane_coverage`, `lanes`,
  `rois`, `counting_lines`, `stop_lines`. Each geometry entity contributes
  `{id, revision, config_hash, **versioned_payload()}` taken **verbatim** from the
  frozen ADR-021 payload — no re-derivation.
- **Excludes** secrets/credentials, audit records, user PII, and unrelated topology.
- **Hash** = `apps.common.versioning.canonical_hash(payload)` (sorted keys, compact
  separators) → `snapshot_hash` (unique).
- **Deduplicated by content hash** (D3): identical config → the same snapshot row is
  reused; a session FK references it (`PROTECT`).
- **Immutable:** `save()` raises on any post-create update. Later Phase-3 config
  edits bump the live entity's `revision`/`config_hash` but **cannot mutate a stored
  snapshot** (it holds copies, no write-back).

## Consequences
Deterministic + reproducible: processing results are bound to a point-in-time config
identity. Enables future "process against snapshot X" without redesign. Snapshots are
single-digit KB (geometry capped at 512 vertices via `common/geometry.py`).

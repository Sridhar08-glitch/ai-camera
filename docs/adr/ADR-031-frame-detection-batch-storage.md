# ADR-031 — FrameDetectionBatch Storage

**Status:** Accepted (Phase 6)

## Context
The detector produces per-frame results that must be durable, queryable, traceable to
their source (session/video/frame/timestamp) and to the producing provider/model
identity, and bounded so a long video cannot bloat the database or a single row. It must
also be purgeable under the retention engine, and must clearly distinguish deterministic
TEST output from real detections.

## Decision
`apps.processing.models.FrameDetectionBatch` — **one row per processed frame**:

- **Provenance FKs:** `session` (PROTECT), `video` (PROTECT), `model_version`
  (PROTECT, nullable — null for the TEST provider). `provider_name` / `provider_version`
  denormalize the producing identity; **`is_test_provider`** flags deterministic TEST
  output (surfaced to the API/frontend banner).
- **Identity:** `source_frame_index` (authoritative decode index) + `pts_seconds`
  (authoritative source time) + `taxonomy_version`.
- **Payload:** `detections` is a bounded JSON list of `Detection.to_dict()` (normalized
  XYXY + canonical class + confidence); `detection_count` is stored for cheap filtering.
  NMS + a `CV_DETECTOR_MAX_DETECTIONS` cap bound the list size per frame.
- **Integrity/indexing:** unique `(session, source_frame_index)`; indexes on
  `(session, source_frame_index)` and `(video, source_frame_index)`.
- **Write pattern:** the `DetectionFrameProcessor` buffers rows and `bulk_create`s every
  `CV_DETECTOR_PERSIST_EVERY_N` frames (+ a final flush), with `ignore_conflicts=True`
  so a re-run over an already-persisted frame is a no-op, never a per-frame DB write.
- **Retention:** `DataCategory.DETECTION_METADATA` + `DetectionMetadataRetentionHandler`
  (registered at app-ready) provide bounded, dry-run-aware purge. No policy is seeded, so
  nothing is purged until an admin configures one.

## Consequences
- Storage is DB-only (no blob/file), so retention is a simple bounded row delete.
- Empty detections are a valid stored result (`detection_count=0`), never a failure.
- Analytics/tracking/counting are **out of scope** for Phase 6 — this table stores raw
  per-frame boxes only; higher-order products are later phases.

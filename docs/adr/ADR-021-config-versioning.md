# ADR-021 — Configuration Versioning Strategy

**Status:** Accepted (Phase 3)

## Decision (D3 = Option B-lite)
Geometry/config-bearing network entities (`Lane`, `Camera`, `RegionOfInterest`,
`CountingLine`, `StopLine`) carry:
- `revision` — `PositiveIntegerField`, starts at 1, **increments only when a
  version-controlled field actually changes** (computed by comparing the new
  `config_hash` to the stored one on save).
- `config_hash` — deterministic sha256 over the **canonical serialization**
  (sorted keys, stable separators) of that entity's version-controlled fields.

## Version-controlled fields per entity (frozen)
- **Lane:** road_segment_id, approach_id, lane_index, direction, lane_type,
  geometry, width_m, speed_limit_override_kph.
- **Camera:** city_id, intersection_id, zone_id, location_lat, location_lng,
  bearing_deg, camera_type, source_type.
- **RegionOfInterest:** camera_id, roi_type, polygon, lane_id.
- **CountingLine:** camera_id, lane_id, start, end, counting_direction.
- **StopLine:** camera_id, approach_id, lane_id, line.

`is_active`, timestamps, `name`, and `metadata` are **not** version-controlled
(archiving/renaming does not bump `revision`).

## Explicit limitation (per approval)
`revision` + `config_hash` provide **change detection, identity, and
traceability** — they do **NOT** preserve previous field values after a mutable
record changes. Phase 3 therefore does **NOT** provide complete historical
configuration reconstruction. A future `ProcessingSession` may reference
`(entity_id, revision, config_hash)` to detect whether config changed since
processing, but cannot reconstruct the exact prior geometry from these fields
alone.

## Future snapshot trigger
Before production CV processing that requires exact point-in-time reconstruction,
introduce an **immutable configuration snapshot** (e.g., `CameraConfigSnapshot`
capturing the full versioned payload at session start) or equivalent. This is
**deferred** in Phase 3 (implementation analysis shows no current consumer needs
full reconstruction — no processing exists yet). Not an event-sourcing system.

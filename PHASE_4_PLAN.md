# PHASE 4 — VIDEO SOURCE ABSTRACTION + UPLOAD + VALIDATION — IMPLEMENTATION PLAN

**Project:** AI Traffic Intelligence & Management Platform
**Phase:** 4 — Video Source Abstraction + Upload + Validation (per frozen Phase 0 §40)
**Depends on:** Phase 0 (frozen, authoritative), Phases 1–3 (COMPLETE)
**Status:** READY FOR REVIEW — planning only; no code, migrations, deps, downloads, or edits to existing files.

> **Scope correction applied:** Phase 4 and Phase 5 remain **separate** per the frozen Phase 0 roadmap. This plan implements **recorded-video ingestion & management only**. All processing (ProcessingSession, snapshots, pipeline, frame iteration/sampling, cancellation, CV runtime, GPU, AI) is **deferred to Phase 5** — see §21 "Phase 5 Prerequisites and Deferred Work." No ADR-024 roadmap merge is created; the frozen roadmap is unchanged.

---

## 1. Current State Verified

Inspected the live repository + environment (not just reports).

- **Baseline tests:** **161 passed, 0 failed, 0 skipped**. Ruff clean.
- **Apps (9):** `accounts`, `audit`, `common`, `governance`, `health`, `network`, `observability`, `realtime`, `retention`.
- **Existing storage abstraction:** `governance.StoredArtifact` — minimal registry `{category, path, checksum_sha256, size_bytes, created_at}`, no storage engine, no lifecycle state. `settings.ARTIFACT_ROOT`; `governance.checksums.validate_artifact_path` (traversal guard) + `sha256_file`. Django `STORAGES` default local FileSystemStorage.
- **Existing artifact abstraction:** StoredArtifact registry only — no VideoAsset, no StorageBackend interface.
- **Reusable foundations:** audit (`record_audit`, EventTypes), RBAC (`IsSystemAdmin`, `HasAnyRole`, `NetworkReadOrAdminWrite` pattern), retention registry + handlers (dry-run/bounded/kill-switch/floors), observability collectors (allowlisted labels), `DataCategory` (incl. `RAW_VIDEO`, `EVIDENCE_MEDIA`), envelope renderer + `StandardPagination`, `UUIDTimeStampedModel`, `common.versioning.canonical_hash`, Channels.
- **Camera available for reuse:** `network.Camera` (metadata only, no credentials) — optional association target for a VideoAsset.
- **Decoder environment:** **NONE installed** — `cv2`, `av` (PyAV), `imageio_ffmpeg` all absent; no `ffmpeg`/`ffprobe` on PATH. Any validation/probe dependency must be added (D2).
- **ADRs:** 001, 002, 011, 013–021. **Next available = ADR-022.**
- **AI/CV present?** **NONE** (no detection/tracking/inference/weights anywhere).
- **Discrepancies:** none between implementation and reports. (The earlier Phase 4 scope-vs-frozen-roadmap mismatch is now resolved by keeping phases separate — this plan matches frozen Phase 0.)

---

## 2. Frozen-Roadmap Alignment

Frozen Phase 0 §40: **Phase 4 = "Video Source Abstraction + Upload + validation"**; **Phase 5 = "Processing Session Engine + CV Runtime skeleton + GPU manager."** This plan implements exactly Phase 4 and defers all Phase-5 items (§21). No roadmap-refinement ADR is created; the frozen architecture stays authoritative.

---

## 3. Phase 4 Objectives

Secure, local-first **recorded-video ingestion & management**: uploaded local video files → validated (signature + decodability) → stored under a swappable local `StorageBackend` with server-generated content-addressed keys → basic metadata extracted for validation → optional single thumbnail → durable `VideoAsset` with a validation lifecycle, camera association, archive behavior → integrated with retention, audit, observability, RBAC → REST APIs + management frontend → capacity/quota/disk safety, filename/traversal safety, orphan reconciliation → comprehensive tests + clean migration. **No processing.**

---

## 4. Explicit Non-Goals (Phase 4 — all deferred to Phase 5+)

ProcessingSession / state machine / ProcessingConfigSnapshot; processing queue / dedicated processing worker / CV runtime; FrameProcessor / ProcessingPipeline; full frame iteration / frame sampling / processing FPS / progress / cancellation / heartbeats / worker-loss detection / watchdog / CV task dispatch; GPU management; vehicle detection / object tracking / any AI model / any external AI API; RTSP / CCTV / NVR / webcam / live streaming; playback streaming / HLS/DASH; Operations Center / digital twin / detection overlays. **A video upload is NOT a processing run.**

---

## 5. Video Source Architecture (Decision D5)

Camera (Phase 3, no creds) stays distinct from the technical source. **Recommendation: VideoAsset-only for Phase 4** — an uploaded `VideoAsset` *is* its source; no separate `VideoSource` record for uploaded files. A `source_type` controlled vocabulary lives on `VideoAsset`: `uploaded_file` (active) with `rtsp`, `webcam`, `nvr`, `disk_path` **reserved inactive/unimplemented** (no fake live sources). A dedicated `VideoSource` model (live-source config + secure credential references) is deferred to when live sources arrive. Credentials never live on Camera or VideoAsset. Camera↔VideoAsset is an **optional** association.

---

## 6. Video Asset Model

`ingestion.VideoAsset` (UUID PK + timestamps):
- Identity: `original_filename` (display only, sanitized), `storage_key` (server-generated, content-addressed), `stored_artifact` (FK → StoredArtifact, authoritative for path/checksum/size), `camera` (FK, SET_NULL, optional), `source_type` (default `uploaded_file`), `uploaded_by` (FK User, SET_NULL), `uploaded_at`.
- File facts (read-through from StoredArtifact, not re-authored): `size_bytes`, `checksum_sha256`.
- Sniffed/probed: `mime_detected` (signature sniff, NOT client), `container_format`, `codec`, `duration_s`, `width`, `height`, `fps`, `frame_count`.
- Lifecycle: `validation_status` (`pending`/`valid`/`invalid`/`quarantined`), `is_active` (archive flag), `error_code`, `error_message` (sanitized).
- Preview: `thumbnail_artifact` (FK StoredArtifact, nullable), `has_thumbnail`.
- Time provenance: `recording_started_at` (nullable, optional) + `recording_time_source` provenance — never invented.
- Privacy: `privacy_status` (`raw_unprocessed` default; `anonymized` reserved — not implemented).

Rules: never trust client MIME/filename/extension; storage filename = server-generated key; original filename kept for display only. (No processing-eligibility/processing fields — that is Phase 5.)

---

## 7. Storage Architecture (D1)

**Recommendation: local filesystem via a `StorageBackend` interface, content-addressed keys.**
- `ingestion.storage.StorageBackend` (ABC): `save(fileobj, key)`, `open(key)`, `delete(key)`, `exists(key)`, `size(key)`, `checksum(key)`, `resolve_path(key)` (internal only). First impl: `LocalFileSystemBackend` rooted at `settings.VIDEO_STORAGE_ROOT` (default `<BASE_DIR>/media/videos`, git-ignored).
- **Content-addressed sharded keys:** `sha256[:2]/sha256[2:4]/sha256.<ext>` — server-generated, no client input in the path, dedupes physical bytes. `resolve_path` confined under the root (traversal-guarded, reusing the Phase 2 `validate_artifact_path` pattern).
- **No absolute filesystem paths exposed via any API** — clients see the VideoAsset UUID + logical metadata only. Interface is provider-swappable later (object/NAS/edge) without touching ingestion business logic. ADR-022.

## 8. StoredArtifact Integration (§27 orig.)

- **StoredArtifact authoritative for physical-file facts:** `path` (= storage_key), `checksum_sha256`, `size_bytes`, `category`. Extended minimally with `state` (`present`/`orphaned`/`deleted`) for lifecycle + orphan reconciliation (additive, backward-compatible).
- **VideoAsset authoritative for video/domain metadata** (duration/fps/resolution/codec/validation/privacy); references its StoredArtifact and does not duplicate checksum/size as source of truth.
- Thumbnails are their own StoredArtifact (`category=VIDEO_THUMBNAIL`) referenced by `VideoAsset.thumbnail_artifact`. Single ownership per fact.

## 9. Upload Security

Validated **before persistence** (pre-decode): reject zero-byte; enforce `MAX_UPLOAD_BYTES`; **file-signature sniff** (magic bytes) for allowed containers; extension/MIME advisory only (mismatch logged, not trusted); sanitize original filename (display-only, never used as path); reject path-traversal in any client field; stream to a **temp file** (never fully in memory) with tuned `DATA_UPLOAD_MAX_MEMORY_SIZE`; compute sha256 while streaming; capacity preflight (§16).
Validated **at probe** (decoder): container/codec actually openable and basic metadata extractable; unreadable/corrupt → `validation_status=invalid` + clear error (never persist a "valid" asset). Interrupted uploads clean up their temp file (finally-block + orphan sweep). Allowed containers/codecs from a configurable allowlist (default mp4/mov/mkv/avi; H.264/H.265/MPEG-4) — others rejected clearly.

## 10. Validation/Probe Decoder Technology (D2 — scoped to ingestion only)

Nothing installed. Phase 4 needs a decoder **only** to (a) confirm an upload is a genuinely readable video, (b) extract basic metadata for validation, (c) optionally grab one thumbnail frame. **No frame iteration / sampling / pipeline (Phase 5).**

| Option | Readability check | Basic metadata | 1-frame grab | Install (Win) | License |
|---|---|---|---|---|---|
| **PyAV (`av`)** — probe-scoped | open container/stream | accurate (stream) | decode 1 frame | pip wheel bundles FFmpeg | PyAV BSD-3; bundled FFmpeg LGPL/GPL — review before commercial dist |
| OpenCV-headless | VideoCapture open | `CAP_PROP_*` (fps/frame_count often approximate) | `read()` 1 frame | pip wheel bundles FFmpeg | Apache-2.0; FFmpeg LGPL |
| ffprobe/ffmpeg subprocess | ffprobe parse | highest | ffmpeg 1 frame | **requires external FFmpeg (absent)** | cleanest (user-provided) but heavier setup |

**Recommendation: PyAV, used strictly for ingestion validation + metadata probe + optional single-frame thumbnail.** Rationale: single self-contained dependency, accurate stream metadata, no system FFmpeg needed, and it is the natural probe tool Phase 5 will also use (no throwaway). **Usage is deliberately limited** — open container, read stream metadata, decode at most one frame for a thumbnail; **the full frame-iteration/processing decoder architecture is a Phase 5 decision** (a separate ADR later). **Documented alternatives:** OpenCV-headless (lighter API, less accurate metadata) if PyAV wheels fail on the target Windows box; ffprobe-subprocess (external FFmpeg) as the license-clean path. **No fake fallback:** if no decoder is importable/functional, validation **fails clearly** (`decoder_unavailable`) — never a synthetic "valid." ADR-023.

**FFmpeg note:** functionality comes from PyAV's **bundled** libav — no system PATH binary, no runtime downloads. Availability detected at startup (import `av`, report version; surface a `decoder` check in `/api/readyz`). The bundled-FFmpeg license must be reviewed before commercial redistribution (mitigation: self-built LGPL FFmpeg or the ffprobe path) — ADR-023 action item; nothing installed during planning.

## 11. Metadata Extraction & Validation Lifecycle

Extract only what validation/management needs: `container_format`, `codec`, `duration_s`, `width`, `height`, `fps`, `frame_count` (best-effort; VBR frame-count caveat documented). Lifecycle: `pending` (row created) → probe → `valid` (readable + metadata ok) or `invalid` (unreadable/unsupported, with error_code) or `quarantined` (signature-mismatch/policy). Only `valid` assets are retained as usable; `invalid` may be auto-cleaned (file removed, row kept for audit or removed per policy).

## 12. Thumbnail Decision (D3)

**Recommendation: generate one thumbnail** at successful probe: a single mid-point/first-keyframe frame, downscaled (≤640px), stored as StoredArtifact (`category=VIDEO_THUMBNAIL`), referenced by `VideoAsset.thumbnail_artifact`, retention-managed, deleted with the video. Cheap (one frame decode + resize via PyAV), high UI value for confirming uploads. No transcoding, no preview clips, no multi-size. (If you prefer zero decode surface in Phase 4, D3 can be "no thumbnail" — metadata-only — but a single thumbnail is low-cost and useful.)

## 13. API Contracts

`/api/v1/` (envelope, paginated, JWT):
- `POST /videos` (multipart upload; size-limited; streams to temp; signature+decode validate; probe metadata; optional thumbnail; returns VideoAsset).
- `GET /videos` (filter: camera, validation_status, is_active, source_type), `GET /videos/{id}`, `GET /videos/{id}/metadata`, `GET /videos/{id}/thumbnail` (authenticated image bytes).
- `POST /videos/{id}/archive` (archive), `DELETE /videos/{id}` (system_admin hard delete, with file cleanup).
**No `/process` endpoint and no processing-session resources** (Phase 5). Multipart via streaming upload handlers; **no raw filesystem paths** in any response. Upload dedupe via checksum (D4).

## 14. Permission Matrix

Traffic video is privacy-sensitive → viewer gets **no** video access.

| Capability | system_admin | traffic_admin | operator | analyst | incident_op | viewer |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Upload video | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Read video metadata | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| View thumbnail | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Download original | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Archive video | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Hard delete video | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

Server-side enforced. (No "start/cancel processing" rows — Phase 5.) Rationale: operators upload/manage; analysts/incident read metadata; **viewer excluded from raw traffic video (privacy)**; original download restricted; hard delete system_admin only.

## 15. Privacy / Data Governance

No claim of anonymity. Controls: viewer excluded; original-download restricted (matrix); `privacy_status` field (`raw_unprocessed`; `anonymized` reserved); future anonymization hook reserved (interface point, not implemented); `RAW_VIDEO` retention category; all access to originals/thumbnails audited; opaque storage keys, never path-exposed. Download permission separate from metadata read.

## 16. Storage Capacity Safety

Configurable: `MAX_UPLOAD_BYTES` (per file), `VIDEO_STORAGE_QUOTA_BYTES` (**global** total), `MIN_FREE_DISK_BYTES` (reserve). **Preflight before accepting an upload:** reject if `content_length > MAX_UPLOAD_BYTES`, if `current_usage + size > quota`, or if `free_disk - size < MIN_FREE_DISK_BYTES` (clear 413/507-style error). Global quota first (simpler); per-user reserved. Prevents silently filling the laptop disk. Usage tracked from StoredArtifact sizes (authoritative) + periodic reconcile.

## 17. Duplicate Handling (D4) & Transaction/Cleanup

- **Duplicate (D4): reject exact-checksum duplicates by default** (409 referencing the existing VideoAsset id). Content-addressed storage dedupes physical bytes; the logical layer rejects to avoid shared-ownership/retention complexity. Configurable to "reuse" later. Never filename-based.
- **Cleanup / transaction boundaries:** FS and Postgres are not one transaction. **Order:** stream to temp → checksum → capacity check → **save to storage (content key)** → **then** create DB rows in a transaction; on DB failure, delete the just-saved file (compensation). If probe fails after save → mark `invalid` + schedule file cleanup. An **orphan-reconciliation** Celery-beat job finds StoredArtifacts marked present with no live owner (and temp files older than T) → cleans up, and flags DB rows whose files are missing → `file_missing`. FS/DB explicitly compensated, never pretended atomic. **No orphan files after DB delete.**

## 18. Retention Integration

New `DataCategory` value: `VIDEO_THUMBNAIL` (RAW_VIDEO exists). Handlers (Phase 2 registry):
- `RAW_VIDEO` — default long, user-controlled; deletes the file via StorageBackend **then** the DB row (no orphans); safety floor; dry-run/bounded/kill-switch inherited.
- `VIDEO_THUMBNAIL` — tied to its video's lifecycle.
An archived video may be retention-eligible; a `valid` active video is protected per policy. (No PROCESSING_SESSION category — Phase 5.)

## 19. Audit & Observability Integration

- **Audit** (new EventTypes): `video_uploaded`, `video_validation_failed`, `video_archived`, `video_deleted`. Metadata = ids + status + error_code + short checksum + changed fields; **never full paths/secrets/large dumps**.
- **Observability** (bounded, allowlisted labels): `videos_uploaded_total`, `upload_failures_total{reason}`; summary `upload_bytes` (sum). **No video-id labels** (per-asset detail lives on the record). (No processing/decode-FPS metrics — Phase 5.)

## 20. Frontend Scope

`/admin/videos` (list + upload form with client-side size guard + upload progress) and `/admin/videos/{id}` (metadata + thumbnail + validation status + archive/delete). Reuses Phase 1/2/3 `apiFetch`, envelope, auth; role-gated (upload for admin+operator; metadata/thumbnail read per matrix; viewer excluded). **No** processing UI, detection overlays, live camera, RTSP setup, playback streaming, or Operations Center.

---

## 21. PHASE 5 PREREQUISITES AND DEFERRED WORK

The following were removed from Phase 4 and are **deferred to Phase 5** (frozen Phase 0 = "Processing Session Engine + CV Runtime skeleton + GPU manager"). Preserved here as the Phase-5 backlog so nothing is lost:

- **ProcessingSession** domain model + strict **state machine** (PENDING→QUEUED→RUNNING→CANCELLING→CANCELLED/COMPLETED/FAILED) with service-level + DB-level transition enforcement.
- **ProcessingConfigSnapshot** — the immutable, canonical, versioned snapshot of the camera/lane/coverage/ROI/counting-line/stop-line configuration, captured **when a ProcessingSession is created/started** (the point a video becomes bound to a specific traffic configuration). **This is the resolution of the Phase 3 versioning limitation and is a Phase 5 prerequisite — do NOT implement in Phase 4.**
- **Processing execution substrate** — dedicated processing queue / dedicated worker / standalone **CV runtime** process + **GPU resource manager** (ADR-002 data plane).
- **FrameProcessor / ProcessingPipeline**, **full frame iteration**, **frame sampling** (every-frame/every-Nth/target-FPS), **source-frame/PTS mapping**, **processing FPS**.
- **Progress reporting** (bounded), **cancellation** (cooperative, honored in the decode loop), **heartbeats**, **worker-loss detection**, **watchdog**, **CV task dispatch** + duplicate-dispatch prevention.
- **Decoder full architecture** — Phase 4 uses PyAV strictly for validation/metadata/thumbnail; the complete decode/iterate strategy, seeking, and performance tuning are a Phase 5 decision.
- **Timestamp model for processing outputs** (video-relative vs real-world) beyond the optional `recording_started_at` metadata stored in Phase 4.
- **Detection/tracking/measurement processors**, any AI model / external AI API, GPU — Phase 6+.

**Phase 5 ADRs (reserve next available numbers when Phase 5 begins), e.g.:** Processing Session Architecture; CV Runtime Boundary; Immutable Processing Configuration Snapshot. **Phase 4 does NOT create ADR-024.**

---

## 22. Windows-First Considerations

Verify: PyAV wheel imports on Python 3.12/Windows; paths with spaces (`E:\ai camera`) handled (always `Path`/content-addressed keys, no user paths); Windows **file locking** (open handles closed in `finally`; probe/thumbnail release the file before any delete); temp files under a controlled dir with `atexit`/finally cleanup; large-file streaming (no full-memory reads); cleanup after process exit (orphan sweep). Linux portability preserved (pathlib + StorageBackend, no OS-locked APIs).

## 23. Repository Changes

New app `ingestion` (VideoAsset, StorageBackend + LocalFileSystemBackend, upload/probe/thumbnail, serializers/views/urls/permissions, capacity helpers, tasks for orphan sweep). Additive edits: `INSTALLED_APPS` (+1), `config/urls.py` (+routes), `config/celery.py` (orphan-reconciliation beat), settings (storage/quota/decoder/limits), `common/datacategories.py` (+`VIDEO_THUMBNAIL`), `audit/models.py` (+4 EventTypes), `governance` StoredArtifact extension (`state`), retention handler registrations, observability collector names. New frontend pages + `videoApi.ts`. New `requirements` entry (PyAV). ADR-022, ADR-023.

## 24. Models and Migrations Expected

- `ingestion/0001` — VideoAsset.
- `governance/000X` — StoredArtifact `state` field (additive).
DataCategory + EventType additions require no migration. Expected: **~2 migrations**. Clean apply on empty DB as `aitraffic_app` verified in §29.

## 25. Dependencies and License Review

| Dep | Proposed version | Purpose (Phase 4) | License | Windows | Note |
|---|---|---|---|---|---|
| **av (PyAV)** | pin latest py3.12-compatible (e.g., `av==13.x`) | **validation readability + metadata probe + 1 thumbnail only** | PyAV **BSD-3**; bundled FFmpeg **LGPL/GPL** | wheels (py3.12) | review bundled-FFmpeg license before commercial redistribution; ffprobe/external-FFmpeg mitigation |
| (alt) opencv-python-headless | — | lighter fallback if PyAV wheel fails | Apache-2.0 + LGPL FFmpeg | wheel | metadata less accurate |

**No external AI dependencies. No processing-worker/queue additions** (separation removed those). Exact version pinned + verified against Python 3.12/Windows at install time; resolved versions recorded in the verification report. Nothing installed during planning.

## 26. ADRs Required

- **ADR-022 — Video Storage Architecture** (local FS + StorageBackend interface + content-addressed keys + StoredArtifact authority + orphan reconciliation).
- **ADR-023 — Video Validation and Metadata Strategy** (PyAV probe-scoped for validation/metadata/thumbnail; FFmpeg-as-bundled-library + license review; ffprobe/OpenCV alternatives; no-fake-fallback; explicitly NOT the Phase-5 processing decoder architecture).
**ADR-024 is NOT created.** Phase-5 ADRs (Processing Session Architecture, CV Runtime Boundary, Immutable Processing Configuration Snapshot) use the next available numbers when Phase 5 begins.

## 27. Testing Strategy

- **Upload:** valid; zero-byte; invalid/fake extension; bad MIME; corrupt; oversized (>MAX); duplicate (409); unsafe filename/traversal; capacity-exceeded rejection.
- **Metadata:** duration/fps/resolution/frame-count/codec/container on a **tiny committed fixture video** (a few generated frames, deterministic, checked into fixtures — no network/large assets).
- **Storage:** save/read/delete/exists/size/checksum; missing file; compensation cleanup on DB failure; orphan reconciliation.
- **Validation lifecycle:** pending→valid/invalid/quarantined transitions; invalid asset not persisted as usable.
- **Thumbnail:** generated on valid upload; absent on invalid; retained/cleaned with the video.
- **Security:** permission matrix (upload/read/download/delete per role incl. viewer-denied); unauthorized upload 403; path non-disclosure (no absolute paths in any response); retention safety.
- **Regression:** all **161** existing tests remain green; none removed/weakened.

## 28. Failure-Testing Strategy

Decoder missing (simulate import failure → `decoder_unavailable`, upload rejected/invalid, no fake success); file removed after upload (`file_missing` via reconciliation); corrupt file post-ingestion; disk capacity insufficient (mock free-space → rejection); storage permission denied; DB failure after file save → compensation deletes file; cleanup-failure path logged + reconciled. **No faked success when infra is unavailable.**

## 29. Verification Procedure

Full suite under `aitraffic_app` (161 + new); upload the fixture video via API → assert stored (content key, checksum), probed metadata, thumbnail; upload duplicate → 409; oversized/capacity → rejection; corrupt/decoder-missing → clear invalid/failure; archive + hard-delete → file removed, no orphan; verify no absolute paths in responses; permission matrix (incl. viewer-denied); retention dry-run on RAW_VIDEO; clean migrate on empty throwaway DB as `aitraffic_app`; Windows checks (spaces path, file locking, cleanup). Report in Phase 0 §13 format with an explicit "no ProcessingSession / no AI / no RTSP / no detection introduced" statement.

## 30. Security & Performance Considerations

**Security:** never trust filename/extension/MIME; server-generated content-addressed keys; signature sniffing; traversal guards; no path disclosure; sanitized errors; strict matrix (viewer excluded); download restricted; size + global quota + free-space reserve (disk-exhaustion guard); temp-file cleanup; audited access; all Phase 1–3 properties preserved.
**Performance:** streaming uploads (no full-memory); one-frame thumbnail only; content-addressed dedupe; indexes on VideoAsset(checksum, camera, validation_status, is_active); pagination caps responses. No premature optimization.

## 31. Implementation Order

1. Confirm 161 baseline. 2. ADR-022, ADR-023. 3. StorageBackend + LocalFS + StoredArtifact `state` extension. 4. Decoder probe (PyAV) install + Windows import verify (validation/metadata/thumbnail only). 5. VideoAsset model. 6. Upload ingestion (security, capacity, temp, checksum, dedupe, compensation). 7. Metadata probe + validation lifecycle. 8. Thumbnail. 9. Audit integration. 10. Retention handlers + `VIDEO_THUMBNAIL` category. 11. Observability collectors. 12. Orphan-reconciliation beat task. 13. APIs + permissions. 14. Frontend (videos list/upload/detail). 15. Tests (unit/integration/security). 16. Full regression. 17. Failure tests. 18. Clean migration verify (empty DB, aitraffic_app). 19. Windows behavior verify. 20. Verification report.

## 32. Acceptance Criteria (AC4-1 … AC4-20)

1. All **161** existing tests remain green. 2. Frozen Phase 0 scope honored (ingestion only; no processing). 3. Storage architecture resolved (ADR-022). 4. Validation/metadata decoder strategy resolved (ADR-023). 5. Uploaded videos stored securely (content-addressed, local backend). 6. Client filenames cannot control storage paths. 7. File content validated beyond extension/MIME (signature + decodability). 8. Basic metadata extraction works on supported videos. 9. Corrupt/unsupported videos fail clearly (no fake valid). 10. Duplicate uploads rejected (409). 11. Size/quota/free-disk limits enforced with clear rejection. 12. Filename sanitization + path-traversal protection enforced. 13. Optional thumbnail generated for valid uploads (if D3=yes). 14. Validation lifecycle enforced. 15. Retention integrated; no orphan files after DB delete; storage cleanup/compensation works. 16. Permissions enforced server-side (viewer excluded from video). 17. Significant operations audited (no paths/secrets). 18. Metrics remain bounded. 19. Frontend upload/management workflow works. 20. **No ProcessingSession / snapshot / pipeline / CV runtime / AI model / AI API / RTSP / CCTV / webcam / detection / tracking introduced.** Plus: full suite passes; clean migration passes. *(Not complete if any mandatory criterion fails.)*

## 33. Expected Deliverables

`ingestion` app (VideoAsset, StorageBackend/LocalFS, upload/probe/thumbnail, serializers/views/urls/permissions, capacity helpers, orphan-sweep task); StoredArtifact `state` extension; audit/retention/observability integration; APIs + permissions; frontend video pages; ADR-022, ADR-023; requirements (PyAV, probe-scoped); dev/setup notes; tests + green regression; `PHASE_4_VERIFICATION_REPORT.md`.

## 34. Known Risks

| ID | Risk | Mitigation |
|---|---|---|
| P4-R1 | PyAV bundled-FFmpeg license for commercial dist | ADR-023 review action; ffprobe/OpenCV alternatives designed |
| P4-R2 | PyAV wheel/Windows import issues | verify import at step 4; OpenCV-headless fallback; fail clearly if none |
| P4-R3 | FS/DB non-atomic → orphans | save-then-DB + compensation + beat orphan sweep + missing-file flag |
| P4-R4 | Disk exhaustion on laptop | max-size + global quota + free-space preflight |
| P4-R5 | Windows file locking on delete | close handles in finally; probe/thumbnail release before delete |
| P4-R6 | Privacy exposure of raw video | viewer excluded, download restricted, audited, anonymization hook reserved |
| P4-R7 | Frame-count/fps inaccuracy (VBR) | PyAV stream metadata; document best-effort; not relied on for processing (Phase 5) |
| P4-R8 | Scope creep into Phase 5 | explicit non-goals + §21 deferral; no processing code |

## 35. Estimated Implementation Effort (revised — ingestion only)

Solo + AI assist, this laptop, ~4–8 hrs/day. Estimates, not guarantees.

| Area | Optimistic | Realistic | High-complexity |
|---|---|---|---|
| ADR-022/023 + StorageBackend + StoredArtifact ext | 1.5 d | 3 d | 4.5 d |
| Decoder probe (PyAV) + thumbnail + Windows import verify | 1.5 d | 2.5 d | 4 d |
| VideoAsset + upload security + capacity + dedupe + compensation | 3 d | 4.5 d | 7 d |
| Metadata probe + validation lifecycle | 1 d | 2 d | 3 d |
| Audit + retention + observability + orphan sweep | 1.5 d | 3 d | 4.5 d |
| APIs + permissions | 1.5 d | 2.5 d | 3.5 d |
| Frontend (videos list/upload/detail) | 2 d | 3 d | 4.5 d |
| Tests + failure + regression + Windows + report | 2 d | 3.5 d | 5 d |
| **Total** | **~14 d** | **~24 d** | **~36 d** |

Roughly **3 / 4–5 / 7 weeks** — down from the merged plan's ~41 realistic days (the ~17-day processing block moved to Phase 5).

---

## Decisions Recommended for Approval (revised — processing decisions removed)

### D1 — Video Storage
Local FS via `StorageBackend` interface, content-addressed keys, StoredArtifact authoritative for file facts (ADR-022). *Rationale:* local-first, provider-swappable later, no client path control. *Tradeoff:* object/NAS added later without business-logic change.

### D2 — Validation/Probe Decoder
**PyAV**, used **strictly** for ingestion validation + metadata probe + one thumbnail (not the Phase-5 frame-processing architecture). Alternatives: OpenCV-headless (lighter, less accurate) / ffprobe-subprocess (license-clean, heavier). No fake fallback. *Tradeoff:* bundled-FFmpeg license review before commercial dist (ADR-023).

### D3 — Thumbnail
**Generate one thumbnail** at valid upload (mid/keyframe, ≤640px, StoredArtifact, retention-managed). *Alternative:* metadata-only (no decode surface). *Rationale:* cheap, high UI value.

### D4 — Duplicate Videos
**Reject exact-checksum duplicates (409)**; content-addressed storage still dedupes bytes. Configurable to "reuse" later. Never filename-based.

### D5 — Video Source Model
**VideoAsset-only** with a `source_type` vocab (uploaded_file active; rtsp/webcam/nvr/disk reserved inactive). Dedicated `VideoSource` (with secure creds) deferred to live-source phases. *Rationale:* simplest correct model for recorded-file ingestion; no fake RTSP; creds never on Camera/VideoAsset.

**Removed from the prior plan (now Phase 5, not decisions here):** processing runtime (was D3) and immutable configuration snapshot (was D4) — see §21.

*(Every remaining decision has a recommendation. Approving the plan adopts D1=StorageBackend/local, D2=PyAV probe-scoped, D3=one thumbnail, D4=reject duplicates, D5=VideoAsset-only.)*

---

## Requested Report Summary

**1. Exact Phase 4 scope:** VideoAsset model; uploaded local video; secure multipart upload; local StorageBackend; StoredArtifact integration; server-generated content-addressed keys; checksum; duplicate detection; file-size limit; storage quota; free-disk protection; filename sanitization; path-traversal protection; file-signature + decodability validation; basic metadata extraction (for validation); optional single thumbnail; camera association; archive behavior; retention integration; audit integration; observability integration; server-side permissions; video-management REST APIs; upload/management frontend; Windows-first storage handling; cleanup + orphan reconciliation; comprehensive tests; clean migration verification.

**2. Exact work deferred to Phase 5:** ProcessingSession + state machine; ProcessingConfigSnapshot (immutable snapshot — created at session creation/start, resolves the Phase 3 versioning limitation); processing queue / dedicated worker / CV runtime + GPU manager; FrameProcessor / ProcessingPipeline; full frame iteration + sampling; processing FPS/progress/cancellation/heartbeats/worker-loss/watchdog; CV task dispatch; the full processing decoder architecture; detection/tracking/AI. (§21.)

**3. Revised decisions requiring approval:** D1 Storage, D2 Validation/Probe decoder, D3 Thumbnail, D4 Duplicate handling, D5 Video source model. (Prior D3 runtime and D4 snapshot removed → Phase 5.)

**4. Revised implementation estimate:** ~14 / 24 / 36 developer-days (optimistic/realistic/high) — ~3/4–5/7 weeks; ~17 processing-days moved to Phase 5.

**5. Revised acceptance criteria:** 20 ingestion-only criteria (§32), no processing criteria; explicit "no ProcessingSession/AI/RTSP/detection" criterion retained.

**6. Dependency changes from separation:** Only PyAV (probe-scoped) remains as a new dependency — added for validation/metadata/thumbnail, not full processing. **Removed vs the merged plan:** no processing-queue/dedicated-worker Celery configuration, no CV-runtime/GPU dependencies, no snapshot/pipeline machinery. FFmpeg-license review note still applies (probe uses bundled libav). No AI dependencies in either version.

---

PHASE 4 PLAN STATUS: READY FOR REVIEW

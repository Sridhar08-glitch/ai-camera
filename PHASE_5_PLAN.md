# PHASE 5 PLAN — Processing Session Engine + CV Runtime Skeleton + GPU Manager

**Status:** DRAFT — READY FOR REVIEW (no implementation performed)
**Date:** 2026-07-15
**Authoritative source:** `PHASE_0_ARCHITECTURE.md` (frozen)
**Scope discipline:** No AI. No detection. No external model/API. No RTSP/CCTV/webcam. Lifecycle + decode + no-AI frame interface only.

---

## 1. CURRENT STATE VERIFIED

I inspected the live repository and the local environment directly (not only the verification reports). A **notable interpreter/environment drift** was discovered and fully investigated (see §1.6).

### 1.1 Test + coverage baseline (re-run live)
Run with the **project interpreter** `backend/.venv/Scripts/python.exe` (Python 3.12.9):

```
188 passed, 0 failed, 0 skipped, 136 warnings in 9.45s
TOTAL coverage: 2903 stmts, 269 miss, 91%
```

This exactly matches the Phase 4 verification report. **The Phase 4 report is accurate.**

> The warnings are benign (`No directory at: staticfiles/`, deprecation filters). No test regressions.

### 1.2 Actual Django apps (10)
`accounts, audit, common, governance, health, ingestion, network, observability, realtime, retention`. **No `processing` / `cv` / `runtime` / `gpu` app exists.**

### 1.3 Actual migration count (12 numbered migrations)
`accounts:2, audit:2, governance:2, ingestion:2, network:1, observability:1, retention:2` (common, health, realtime have none). Chain migrates cleanly from empty DB (verified previously; not re-mutated here).

### 1.4 Actual Phase 4 implementation state (verified by reading source)
- `VideoAsset` (`apps/ingestion/models.py:33`) — UUID PK, `stored_artifact` FK (PROTECT), optional `camera` FK (SET_NULL), metadata fields `duration_s, width, height, fps, frame_count`, `validation_status`, checksum-dedup unique constraint. **Ready to be referenced by ProcessingSession.**
- `StoredArtifact` (`apps/governance/models.py:160`) — UUID PK, `category/path/checksum_sha256/state{PRESENT,ORPHANED,DELETED}`.
- `StorageBackend` (`apps/ingestion/storage.py`) — ABC + `LocalFileSystemBackend`; **`resolve_path(key)` is the exact hook Phase 5 uses to hand a readable filesystem path to PyAV.** `get_storage_backend()` singleton.
- Phase 4 PyAV (`apps/ingestion/probe.py`) — `probe_video()` (metadata), `make_thumbnail()` (one frame), `decoder_available()`; all open→use→`close()` in `finally`. **Probe-scoped only** — no frame iteration/sampling exists.
- Network config models (`apps/network/models/`) — `Camera, Lane, RegionOfInterest, CountingLine, StopLine, CameraLaneCoverage` all carry `revision` + `config_hash` via `VersionedConfigMixin` and expose `versioned_payload()`. Geometry stored as `{"space": "...", "coordinates": [...]}` JSON (image_normalized / geo).
- Retention (`apps/ingestion/retention_handlers.py:15`) — **already contains a reserved Phase-5 hook** `_video_is_protected(asset)` returning `False`, documented "skip assets bound to a non-terminal ProcessingSession."
- Audit `record_audit(...)`, observability `collectors.incr/observe` (strict allowlist), Channels `SystemConsumer` (ws/system/, JWT), health `/api/healthz` + `/api/readyz` (db/redis/celery-heartbeat).

### 1.5 Actual processing-related code
**None.** Phase 5 is greenfield. The only anticipatory artifacts are: the retention protection hook (§1.4), ADR-021's deferred-snapshot note, ADR-023's "not the Phase 5 decoder" note, and ADR-002's "CV runtime arrives Phase 5."

### 1.6 ⚠ Environment drift discovered and resolved
There are **two Python worlds on this machine**; distinguish them carefully.

| Layer | Interpreter | `av` | `torch` | Notes |
|---|---|---|---|---|
| **Global / default shell** (`py -3.14`, first on PATH) | Python **3.14.4** | 17.0.1 | **2.11.0+cu128** | Unrelated machine-level install. `structlog` absent → **cannot even collect the test suite.** |
| **Project runtime** (`backend/.venv`, used by all `scripts/*.ps1`) | Python **3.12.9** | **13.1.0** | **absent** | `pyvenv.cfg` → Python312. Runs 188/188 green. **This is the real project environment.** |
| Base Python 3.12 (`py -3.12`) | 3.12.9 | absent | absent | venv's parent; no project packages. |
| Empty `E:\ai camera\.venv` (root) | — | — | — | Stray empty dir; **not** the project venv. |

**Conclusions (must be reflected in the plan, not "fixed"):**
- The Phase 4 report (Python 3.12.9 / PyAV 13.1.0) is **correct**. The earlier apparent discrepancy was **my shell resolving the wrong global interpreter**, not a report error.
- **PyTorch 2.11.0+cu128 is a machine-level installation, NOT a project dependency.** It is not in `requirements/*.txt`, not imported anywhere in `apps/`, and absent from the project venv. Phase 5 must **not** import it and must **not** be interpreted as "AI already present."
- **Environment-drift action item (do NOT execute during planning):** the project should pin/verify that all Phase 5 tooling runs under `backend/.venv` (3.12.9) and add a guard so an operator does not accidentally run `python manage.py ...` under global 3.14. Documented as a risk (§50), not repaired now.

Four environment categories to keep distinct throughout this plan:
1. **Project-declared** — `requirements/base.txt|dev.txt` (Django 5.2.7, av==13.1.0, celery 5.5.3, redis 6.4.0; **no torch/opencv/ultralytics**).
2. **Project-verified runtime** — `backend/.venv` Python 3.12.9, av 13.1.0.
3. **Current shell/global** — Python 3.14.4 + av 17.0.1 + torch cu128 (ignore for the project).
4. **Machine capability** — see §1.7.

### 1.7 Actual GPU hardware + driver/runtime (verified)
| Fact | Value |
|---|---|
| GPU 0 | **NVIDIA GeForce RTX 3070 Laptop GPU** |
| VRAM | **8192 MiB (8 GB)** — matches Phase 0's "8 GB VRAM" design assumption |
| NVIDIA driver | **592.00** (Win32 driver 32.0.15.9200) |
| `nvidia-smi` | **present**, `--query-gpu` works (name/memory/driver) |
| CUDA (per nvidia-smi/torch) | **12.8** |
| Integrated GPU | AMD Radeon(TM) Graphics (iGPU) |
| `torch.cuda.is_available()` | **True** — but only in the **global** 3.14 env; **irrelevant** to the project venv where torch is absent |

**GPU planning stance:** the Phase 5 GPU manager will detect hardware **independently of any AI framework**, using `nvidia-smi` as an *optional* NVIDIA capability provider, and fall back to CPU cleanly. Phase 5 must not depend on torch/CUDA.

### 1.8 PyAV sequential-decode benchmark (run live, then fixtures removed)
Real, non-destructive benchmark on the project venv (PyAV 13.1.0, bundled libav; `libx264` available). Synthetic `testsrc` clips (CFR). Numbers are an **optimistic upper bound** — synthetic frames compress/decode faster than real H.264 traffic footage — but they establish that **decode is not the Phase 5 bottleneck.**

| Clip | Pure decode | Decode + full RGB convert (every frame) | Decode + convert every 5th |
|---|---|---|---|
| 640×480@30 (300f) | 4255 fps | 1830 fps | 2949 fps |
| 1280×720@30 (450f) | 2546 fps | 560 fps | 1414 fps |
| 1920×1080@30 (600f) | 1865 fps | 265 fps | 741 fps |

Additional verified facts: **PTS present on 100% of frames**; clean `time_base` (`1/15360`); `average_rate` accurate; CFR correctly detected via constant PTS deltas. (Process peak-working-set probe via `K32GetProcessMemoryInfo` returned −1 in this quick harness; **memory profiling is deferred to implementation** using `psutil` — see §18/§39.)

### 1.9 Discrepancies between reports and repository reality
| Claimed | Reality | Verdict |
|---|---|---|
| Python 3.12 / PyAV 13.1.0 baseline | True in `backend/.venv` | ✅ Report correct |
| 188 passed / 91% cov | Reproduced live | ✅ |
| "No ProcessingSession/pipeline/CV runtime/AI" | Confirmed greenfield | ✅ |
| (Implicit) machine has no AI stack | Global torch cu128 present but **not a project dep** | ⚠ Documented, not a contradiction |

---

## 2. RECONCILIATION WITH THE FROZEN PHASE 0 ROADMAP

### 2.1 Authoritative Phase 5 definition (quoted)
> **Phase 5 — Processing Session Engine + CV Runtime skeleton + GPU manager** (lifecycle, heartbeats, recovery; **no detection yet**). Depends: P2, P4. — `PHASE_0_ARCHITECTURE.md:546`

> `ProcessingSession` engine + CV runtime (**START/PAUSE/RESUME/STOP/CANCEL**) with heartbeats. — line 59

> **Phase 6 — Detection provider + Benchmark suite + profile selection. Depends: P5.** — line 547

**Confirmed:** Phase 5 wording is exactly *Processing Session Engine + CV Runtime skeleton + GPU manager*. Detection begins in **Phase 6**.

### 2.2 What belongs to Phase 5 (frozen constraints that bind this plan)
- **Three-runtime split** (ADR-002, §9/§10): Django control plane, Celery short/medium jobs, **dedicated CV runtime** data plane. Django never imports CV/GPU code. Comms via **PostgreSQL (durable) + Redis (commands/heartbeat/pub-sub)** only.
- **Session state machine** (§13) incl. START/PAUSE/RESUME/STOP/CANCEL, **single-writer = CV runtime**, `requested_action` intent column set by Django, idempotent transitions, invalid transitions rejected.
- **GPU Resource Manager** (§14): sole GPU owner (future), single-model/single-session default on 8 GB, VRAM budgeting interface, CPU fallback tagged, `device_id` interface for future multi-GPU (not implemented).
- **Heartbeats + watchdog** (§10/§13/§33): Redis heartbeat key `session:{id}:heartbeat` (TTL); Celery-beat watchdog flags heartbeat-expired RUNNING → FAILED/recoverable.
- **`VideoSource` provider interface** (§12): `open()/frames()->Iterator[Frame]/metadata()/close()`, impl `LocalFileSource`. Frozen as a Protocol here; detection/tracking/etc. providers stay deferred.
- **Immutable config snapshot** (ADR-021 "future snapshot trigger"): Phase 5 is the first consumer needing point-in-time config → build it now.
- **Retention protection** (§17 T1 raw video; existing hook) and **audit/observability/logging** integration.

### 2.3 What remains Phase 6+ (explicit)
DetectionProvider, TrackingProvider, LaneAssociator, SpeedEstimator, measurement/counting, congestion, queue, incident, alerts, analytics, prediction, SUMO, signals, twin, RTSP/edge/multi-GPU. **Also deferred:** live/pause-driven measurement semantics, model benchmark harness, canonical vehicle taxonomy.

### 2.4 Ambiguities + recommended interpretation
1. **State-machine size.** The planning brief (§6) sketched a *smaller* machine (PENDING/QUEUED/STARTING/RUNNING/CANCELLING/CANCELLED/COMPLETED/FAILED) **without pause/resume/stop**. The frozen doc (line 59 + §13) **explicitly includes PAUSE/RESUME/STOP in Phase 5.** → **Recommendation: honor the frozen machine** (implement PAUSE/RESUME/STOP/CANCEL), because (a) frozen is authoritative, (b) these are pure-lifecycle, no-AI operations that are exactly the "execution foundation" Phase 5 must prove, and (c) it avoids a state-machine rewrite in Phase 6. See §6 for the concrete adopted machine and naming reconciliation.
2. **Runtime vs Celery.** Phase 0 explicitly *rejected* "CV in Celery" (line 670: "Celery = short/medium jobs only"). → Phase 5 builds a **dedicated CV runtime process** (D1), not a Celery task. Celery beat is retained **only** for the watchdog (legitimate scheduled maintenance).
3. **ADR numbering.** Phase 0 conceptually earmarked "ADR-003" for the session state machine, but the on-disk ADR series skips to 011–023. → Follow the **actual repo convention: next = ADR-024**; the state-machine decision is realized as **ADR-024** (noted in §40).
4. **Dataset management.** Frozen Phase 0 does **not** require any dataset in Phase 5. → **Excluded** (non-goal).

**No silent expansion into AI. Detection stays Phase 6.**

---

## 3. OBJECTIVES

Prove the platform can reliably drive a complete traffic video through a durable, cancellable, observable processing lifecycle **without any AI**:

Valid `VideoAsset` → create `ProcessingSession` → capture immutable `ProcessingConfigSnapshot` → queue (Django writes QUEUED + publishes command) → CV runtime claims session → open stored video via `StorageBackend.resolve_path` → decode frames (PyAV) → apply sampling → pass frames through a **no-AI `FrameProcessor`** → track source frame index + PTS timestamp → persist bounded progress → honor pause/resume/cancel/stop → detect runtime/worker loss (heartbeat) → complete (or fail conservatively).

Success = **a full traffic video processed frame-by-frame end-to-end with zero vehicle detection**, reproducible config identity, and no resource leaks.

---

## 4. NON-GOALS (frozen)

No YOLO/RT-DETR/any detector; no pretrained model; no external AI API; no vehicle/pedestrian detection; no tracking/counting/speed/queue/congestion/incident/ANPR/face; no prediction/signal optimization; no training/dataset download; no RTSP/CCTV/NVR/webcam/live; no production inference. **No fabricated detections or dummy bounding boxes of any kind.** No torch/CUDA/tensorflow/ultralytics/opencv dependency added. A no-AI frame pipeline is the deliverable.

---

## 5. PROCESSINGSESSION DOMAIN

New app **`apps.processing`**. `ProcessingSession(UUIDTimeStampedModel)` — UUID PK, created/updated timestamps inherited.

**Field ownership legend:** `[D]`=Django/control-plane writes; `[R]`=CV runtime writes; `[S]`=set once at creation (immutable).

| Field | Type | Owner | Notes |
|---|---|---|---|
| `id` | UUID PK | S | domain identity (never expose runtime/task id) |
| `video_asset` | FK→VideoAsset (PROTECT) | S | source; PROTECT so config can't vanish under a session |
| `camera` | FK→Camera (PROTECT, null) | S | denormalized from video/snapshot at creation |
| `requested_by` | FK→User (SET_NULL, null) | S | actor |
| `state` | CharField(choices) | R (except QUEUED←D) | see §6 |
| `requested_action` | CharField(choices, blank) | D | intent bus mirror: PAUSE/RESUME/STOP/CANCEL |
| `config_snapshot` | FK→ProcessingConfigSnapshot (PROTECT) | S | §7 |
| `processing_params` | JSONField (immutable) | S | §9 execution params (sampling etc.) |
| `runtime_id` | CharField(blank) | R | which CV runtime instance claimed it |
| `runtime_version` | CharField(blank) | R | processing/runtime code version |
| `error_code` | CharField(48, blank) | R | stable code (§22) |
| `error_message` | CharField(500, blank) | R | **sanitized**; no paths/secrets |
| `retry_of` | FK→self (SET_NULL, null) | S | §24 lineage |
| `retry_count` | PositiveInt default 0 | S | denormalized depth |
| **Progress (bounded, single-row, rate-limited writes)** | | | |
| `frames_total_estimate` | BigInt null | R | best-effort; may be null (§19) |
| `frames_decoded` | BigInt default 0 | R | |
| `frames_processed` | BigInt default 0 | R | |
| `current_frame_index` | BigInt null | R | last source frame index |
| `current_pts_seconds` | Float null | R | last source timestamp (PTS·time_base) |
| `progress_percent` | Float null | R | null when total unknown |
| `decode_fps` | Float null | R | rolling |
| `processing_fps` | Float null | R | rolling |
| `last_heartbeat_at` | DateTime null | R | durable mirror of Redis heartbeat |
| **Lifecycle timestamps** | | | |
| `queued_at / started_at / paused_at / completed_at / failed_at / cancelled_at / cancel_requested_at` | DateTime null | D/R | one column per meaningful transition |

**Normalization decisions (per the brief's "do not blindly implement all fields"):**
- **`source_fps`, `duration_s`, `width`, `height`, container/codec are NOT copied** onto the session — they already live on `VideoAsset` (immutable there) and, for reproducibility, are captured in the **config snapshot** (§7). Avoid a third copy.
- **`sampling_strategy` / `sampling_config` collapse into `processing_params`** (one immutable JSON) rather than several loose columns (§9).
- **Heartbeat authoritative store = Redis TTL key** (`session:{id}:heartbeat`); the DB `last_heartbeat_at` is a *bounded* durable mirror for the watchdog, updated at the same rate as progress — **not** per frame.
- Per-frame values (`current_frame_index/pts`, fps gauges) are **rapidly changing but bounded**: they live on the single session row and are flushed on a throttle (§19), never per frame. No per-frame table in Phase 5.

Indexes: `(state, last_heartbeat_at)` (watchdog), `(video_asset, state)` (duplicate-active check), `(camera, created_at)`.

---

## 6. PROCESSING STATE MACHINE (adopted)

**Canonical states (frozen §13 naming, minus AI-specific `COMPLETING` semantics kept as a clean shutdown phase):**

```
CREATED → QUEUED → INITIALIZING → RUNNING
                                   RUNNING ⇄ PAUSING → PAUSED → RESUMING → RUNNING
                                   RUNNING → COMPLETING → COMPLETED
Terminal (from applicable states): FAILED · CANCELLED · STOPPED
```

*(Naming reconciliation: the brief's `PENDING`≈`CREATED`, `STARTING`≈`INITIALIZING`, `CANCELLING`≈the `requested_action=CANCEL`+`PAUSING`-style safe-boundary drain. We adopt the frozen names so ADR-024 and Phase 6 stay consistent.)*

**Allowed transitions**
| From | To | Trigger | Writer |
|---|---|---|---|
| CREATED | QUEUED | enqueue (snapshot already captured) | **Django** |
| CREATED/QUEUED | CANCELLED | cancel before pickup | Django (or runtime) |
| QUEUED | INITIALIZING | runtime claims (atomic) | Runtime |
| INITIALIZING | RUNNING | decoder opened OK | Runtime |
| INITIALIZING | FAILED | open/decoder/snapshot failure | Runtime |
| RUNNING | COMPLETING → COMPLETED | last frame processed | Runtime |
| RUNNING | PAUSING → PAUSED | `requested_action=PAUSE` at safe boundary | Runtime |
| PAUSED | RESUMING → RUNNING | `requested_action=RESUME` | Runtime |
| RUNNING/PAUSED | STOPPED | `requested_action=STOP` (graceful terminal) | Runtime |
| RUNNING/PAUSED/INITIALIZING | CANCELLED | `requested_action=CANCEL` | Runtime |
| RUNNING/INITIALIZING/PAUSED | FAILED | error or heartbeat-loss (watchdog) | Runtime/Watchdog |

**Forbidden (rejected + logged as observability event):** any write to a terminal state; RESUME when not PAUSED; RUNNING from CANCELLED/STOPPED/COMPLETED/FAILED; QUEUED→RUNNING skipping INITIALIZING; Django writing any state other than QUEUED/CANCELLED-before-pickup.

**Rules**
- **Single writer = CV runtime.** Django only: `CREATED→QUEUED`, pre-pickup `→CANCELLED`, and sets `requested_action`. Everything else = runtime. This is the frozen anti-race rule.
- **Idempotent:** re-issuing STOP/CANCEL on a terminal session is a no-op (returns current state).
- **Terminal states:** COMPLETED, FAILED, CANCELLED, STOPPED (no exits).
- **Retry:** never re-opens a terminal session; creates a new one (§24).
- **Cancellation/pause = advisory intents** honored at bounded safe frame boundaries (§21).
- **Worker loss:** heartbeat gap → watchdog `RUNNING→FAILED(reason=heartbeat_lost)` (§23).

**Enforcement**
- **One authoritative service layer** `apps/processing/services/state.py::transition(session, to, *, actor, reason)` — the *only* code that writes `state`. Validates the transition table, stamps the matching timestamp, writes an `AuditEvent` + structured log, updates metrics. No serializer/view writes `state` directly.
- **DB guardrails:** `CheckConstraint` limiting `state` to the enum; **partial unique index** enforcing ≤1 concurrently-non-terminal session per configured concurrency (§25); DB default `state=CREATED`.
- **API cannot set arbitrary status** — only the command endpoints (§30) that set `requested_action`; the runtime performs the actual transition.

---

## 7. IMMUTABLE PROCESSING CONFIGURATION SNAPSHOT (mandatory)

Implements ADR-021's deferred "future snapshot trigger." Model **`ProcessingConfigSnapshot(UUIDModel)`** — immutable (no `updated_at`, no update/delete API; ORM `save()` guard blocks post-create mutation).

**Contents (exactly what future CV processing needs — bounded, deterministic):**
```jsonc
{
  "snapshot_schema_version": 1,
  "coordinate_spaces": ["image_normalized"],           // per §12 CoordinateSpace
  "video": {                                            // enough to bind decode identity
    "video_asset_id": "...", "checksum_sha256": "...",
    "fps": 30.0, "duration_s": 20.0, "width": 1920, "height": 1080,
    "frame_count": 600                                  // best-effort, labeled
  },
  "camera": {"id": "...", "revision": 3, "config_hash": "..."},
  "camera_lane_coverage": [{"lane_id":"...","coverage_type":"PRIMARY","priority":0}],
  "lanes":          [{"id":"...","revision":2,"config_hash":"...","direction":"FORWARD","lane_type":"GENERAL","geometry":{...}}],
  "rois":           [{"id":"...","revision":1,"config_hash":"...","roi_type":"DETECTION","polygon":{...},"lane_id":"..."}],
  "counting_lines": [{"id":"...","revision":1,"config_hash":"...","start":{...},"end":{...},"counting_direction":"A_TO_B","lane_id":"..."}],
  "stop_lines":     [{"id":"...","revision":1,"config_hash":"...","line":{...},"approach_id":"...","lane_id":"..."}]
}
```
Geometry blocks are taken **verbatim from each entity's `versioned_payload()`** (already canonical/validated), so the snapshot reuses the exact frozen field set (ADR-021) — no re-derivation.

**Explicitly NOT snapshotted:** secrets/credentials (cameras store none anyway), audit records, user PII, unrelated city/zone/road topology beyond what geometry references, whole ORM objects, mutable `name`/`is_active`/timestamps.

**Model fields:** `snapshot_schema_version:int`, `payload:JSONField` (the object above), `snapshot_hash:CharField(64)` = `canonical_hash(payload)` (reuse `apps.common.versioning.canonical_hash` — sorted keys, compact separators), `created_at`. Size-bounded (geometry capped at `MAX_VERTICES=512` per `common/geometry.py`; a small camera has a handful of ROIs/lines → single-digit KB).

**Properties (all satisfied by design):** immutable · deterministic (canonical JSON) · canonically serialized · versioned (`snapshot_schema_version`) · bounded · hashable (`snapshot_hash`) · reproducible from config-state-at-capture. Post-capture Phase-3 config edits bump the live entity's `revision`/`config_hash` but **cannot mutate a stored snapshot row** (no FK write-back; snapshot holds copies).

**Dedup vs 1:1 → see D3 (recommend content-hash dedup).**

---

## 8. SNAPSHOT CAPTURE BOUNDARY → see D2

**Recommendation: Option A — capture at `ProcessingSession` creation**, synchronously, inside the Django creation transaction. Rationale in D2. The session is invalid without a snapshot (FK is non-null, PROTECT).

---

## 9. PROCESSING PARAMETERS (separate from config)

**Traffic config** → the immutable snapshot (§7). **Execution params** → `ProcessingSession.processing_params` (immutable JSON, set at creation):
```jsonc
{ "sampling": {"mode": "EVERY_N", "n": 5, "target_fps": null},
  "processor": "noop",            // "noop" | "framecount" (Phase 5 only)
  "device_preference": "auto",    // "auto" | "cpu" | "cuda:0" — GPU manager resolves
  "params_version": 1 }
```
Reproducible and auditable (hash included in audit metadata). **Not** merged into mutable settings; **not** stored as loose mutable columns. Validated by a DRF serializer at creation; unknown keys rejected.

---

## 10. CV RUNTIME ARCHITECTURE → see D1

**Recommendation: Option B — a standalone CV runtime process** (`python manage.py run_cv_runtime`) that owns decoding and (future) GPU/models, honoring frozen ADR-002. It:
1. Loads Django settings/ORM (for durable state) but **never serves HTTP and is launched as its own process**.
2. Claims `QUEUED` sessions atomically from PostgreSQL (`SELECT … FOR UPDATE SKIP LOCKED`), respecting concurrency (§25).
3. Subscribes to the Redis **command bus** (`session:{id}:commands` / a runtime control channel) for PAUSE/RESUME/STOP/CANCEL, and also reads `requested_action` from the row (belt-and-suspenders; DB authoritative).
4. Runs the pipeline (§17), posts heartbeats to Redis + bounded DB progress, publishes live progress to Redis pub/sub (`live:session:{id}`).
5. Is the **single writer** of session state.

**Celery** keeps only the **watchdog** (Celery beat, §23) — no CV work in Celery (frozen line 670).

**Why not A (Celery queue):** violates the frozen ADR-002 correction and would force a rewrite once GPU model ownership (Phase 6) needs a long-lived, single-owner process. **Why not C (hybrid dispatch):** frozen contract has Django publish START directly via Redis; inserting Celery as dispatcher adds a hop with no benefit on one laptop.

**Anti-over-engineering:** the "runtime" is a single-process poll+command loop, not a distributed system. Boundary preserved (Postgres + Redis only) so it can later move hosts.

---

## 11. GPU MANAGER → see D9

Framework-independent `apps/processing/runtime/gpu.py::GPUManager`:
- **Detect devices** without importing torch: parse `nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,driver_version --format=csv,noheader,nounits` (subprocess, short timeout). If `nvidia-smi` missing/fails → **CPU mode** (no fake device).
- **Record identity:** name, index, total/used/free VRAM (MiB), driver version.
- **Select device:** honor `processing_params.device_preference`; `auto` → first CUDA device if present else CPU. Phase 5 processors run **CPU-only** regardless (no model), but the manager reports the device the session *would* use and tags the session.
- **Reserve/release logical ownership:** a Redis key `gpu:{index}:owner` (session id, TTL, refreshed by heartbeat) + in-process lock, so a future second heavy job cannot silently grab the same GPU. Released on terminal state / shutdown.
- **Health:** `gpu_status()` → `{available, mode, devices[], reserved_by}` surfaced via API (§33).
- **VRAM budgeting:** interface stub `can_fit(estimated_mb)` returning True on CPU / free-VRAM check on CUDA — **no model load in Phase 5**.
- **`device_id` / multi-GPU:** interface accepts an index; enumeration works, but scheduling stays single-device (frozen "interface only").

No torch/CUDA import. No fabricated detection. `nvidia-smi` is optional.

---

## 12. GPU OWNERSHIP MODEL

Frozen principle adopted: **one CV runtime process is the sole (future) GPU/model owner; Django and Celery never touch CUDA.** Phase 5 loads no models, so ownership is *logical* (the Redis reservation) rather than a loaded model. Default **one heavy session at a time** on 8 GB (§25). Configurable concurrency + CPU-only mode supported; multi-GPU is interface-only. Prefer **correctness + bounded resource use** over concurrency.

---

## 13. VIDEO DECODING → see D4

**Recommendation: continue with PyAV (`av==13.1.0`)** as the full processing decoder, via a `VideoSource` abstraction. Benchmark (§1.8) verified on Windows/3.12: sequential iteration, reliable PTS, correct `time_base`, accurate `average_rate`, CFR detection, clean `close()`. Decode throughput (265 fps @1080p with full pixel conversion) far exceeds any Phase 5 need — **decode is not the bottleneck** (future detection will be). No system FFmpeg required (bundled libav).

**Canonical in-memory frame representation = NumPy `ndarray`, format `rgb24`** (H×W×3, `uint8`, C-contiguous). This is now a **Phase 5 runtime standard** (not deferred to Phase 6): PyAV's `frame.to_ndarray(format="rgb24")` is the idiomatic bridge, `rgb24` is the interchange format every mainstream detector/tracker accepts, and fixing it now means Phase 6 plugs a detector into a stable array contract with **no pipeline redesign**. Conversion is **lazy** — the decoder yields raw `av.VideoFrame`; sampling (§15) runs on metadata **before** any pixel conversion; the ndarray is materialized **only when a processor asks** for it (§16), and **only for sampled frames**. Rationale for `rgb24` over alternatives: it is the model-input lingua franca; `bgr24` (OpenCV-native) is avoided since OpenCV is a non-goal; native `yuv420p` avoids a copy but pushes color-space handling into every processor — rejected for a clean canonical contract, though a processor may still request an alternate format explicitly (§16) when it has a strong reason.

Implementation notes to verify during build: mid-stream corrupt-frame handling; VFR (real PTS, never `frame_number/fps`); resource cleanup in `finally`; and the deferred `to_ndarray` / EVERY_N-with-conversion benchmark rows (§36) once NumPy is installed as the first implementation step.

**Benchmark once more against one real H.264 traffic clip** during implementation to record a realistic (non-synthetic) baseline. No decoder replacement unless a real defect surfaces (OpenCV/ffprobe remain documented fallbacks per ADR-023).

---

## 14. FRAME IDENTITY & TIMESTAMPS

Canonical internal `FrameMeta` (dataclass, passed to every processor):
```
source_frame_index : int      # 0-based decode order from stream start (authoritative sequence)
decoded_index      : int      # count of frames decoded this run (== source_frame_index for sequential)
processed_index    : int      # count of frames that passed the sampler
pts                : int|None  # raw presentation timestamp
time_base          : Fraction # stream time_base
pts_seconds        : float|None# pts * time_base  → relative video timestamp (authoritative time)
approx_seconds     : float     # fallback = source_frame_index / source_fps when pts is None
```
**Rule:** timestamp = `pts * time_base` whenever PTS exists (100% of frames in the benchmark); `frame_number/fps` is used **only** as a labeled fallback for the rare no-PTS stream. Every future detection/measurement will be traceable to `(source_frame_index, pts_seconds)`.

---

## 15. FRAME SAMPLING → see D5

**Recommendation: ship all three** (deterministic):
- **EVERY_FRAME** — process every decoded frame.
- **EVERY_N** — process when `source_frame_index % n == 0`.
- **TARGET_FPS** — emit ≈ requested rate by comparing `pts_seconds` against the last processed timestamp (`accept if pts_seconds - last_processed_pts >= 1/target_fps`), respecting real source time (VFR-safe).

Every processed frame retains full `FrameMeta` (source identity + timestamp). **Frames live in memory only; nothing is written to disk per frame.** Sampler is a pure generator wrapping `VideoSource.frames()`.

---

## 16. FRAME PROCESSING INTERFACE

The processing loop passes a **`FrameView`** — a lazy frame-access wrapper — to every processor. This is the single abstraction that carries the frame through Phase 5 and into Phase 6 detection **without a breaking redesign**:
```python
class FrameView:                          # thin wrapper; NOT premature abstraction
    frame: "av.VideoFrame"                # raw PyAV frame (metadata/plane access, no conversion)
    meta:  FrameMeta                       # source index, PTS, timestamps (§14)
    def as_rgb_ndarray(self) -> "np.ndarray":
        # canonical representation: rgb24, H×W×3 uint8, C-contiguous.
        # lazy + cached: first call = frame.to_ndarray(format="rgb24"); subsequent calls return the
        # SAME cached array (no re-convert, no copy). Never called for un-sampled frames.
        ...
    def as_ndarray(self, fmt: str) -> "np.ndarray":   # escape hatch for a processor with a strong
        ...                                            # reason to want another format (cached per fmt)

class FrameProcessor(Protocol):
    name: str; version: str
    def setup(self, ctx: ProcessingContext) -> None: ...     # ctx: snapshot payload, params, device, logger
    def process(self, view: FrameView, ctx: ProcessingContext) -> ProcessorResult: ...
    def teardown(self) -> ProcessorSummary: ...              # aggregate metrics only
```
`ProcessorResult` = small structured record (**no boxes, no detections**): e.g. `{frame_index, pts_seconds, note}`. Phase 5 ships exactly two **infrastructure** processors:
- **`NoOpFrameProcessor`** — reads only `view.meta`; **never calls `as_rgb_ndarray()`** → zero pixel conversion. Proves metadata/lifecycle flow.
- **`FrameCountProcessor`** — counts processed frames; optionally a cheap deterministic checksum via `bytes(view.frame.planes[0])` (raw-plane, still no conversion) **or** `view.as_rgb_ndarray()` to exercise the canonical path once. No AI, no detection.

**Efficiency invariants (requirements 1–6):**
1. **No automatic conversion** — the decoder yields raw frames; the loop never converts.
2. **Sample before convert** — `Sampler.accept(meta)` (§15) runs on metadata; conversion happens only *inside* `process()` for **accepted** frames.
3. **NoOp needs no NumPy** — metadata/raw-frame processing requires no ndarray.
4. **Pixel processors request the standard array** — `as_rgb_ndarray()` returns the canonical rgb24 ndarray.
5. **No unnecessary copies** — conversion is done **once per frame** and cached in the `FrameView`; multiple processors/stages (Phase 6) share the same array object; `to_ndarray` performs exactly the one unavoidable swscale copy.
6. **Canonical format = `rgb24`** explicitly (alt formats only via the `as_ndarray(fmt)` escape hatch).

Phase 6 adds a `DetectionFrameProcessor` implementing the same Protocol; it simply calls `view.as_rgb_ndarray()` and feeds the detector — **no change** to session lifecycle, decoder, sampler, progress, cancellation, or orchestration. **No plugin/registry framework** beyond a small name→class map keyed by `processing_params.processor`. The `FrameView` is created per decoded frame and dropped immediately after `process()` (§18), so a cached array lives no longer than one loop iteration.

---

## 17. PROCESSING PIPELINE

Minimal, linear (no DAG/workflow engine):
```
VideoSource.open() → for frame in frames(): → Sampler.accept(meta)?
   → FrameProcessor.process(frame, meta, ctx)
   → throttled progress persist + heartbeat  (§19/§23)
   → check requested_action (pause/resume/stop/cancel)  (§21)
   → release frame reference
→ FrameProcessor.teardown() → COMPLETING → COMPLETED   (finally: VideoSource.close(), GPU release)
```
One orchestrator `apps/processing/runtime/pipeline.py::run_session(session_id)`; wrapped in try/finally for guaranteed cleanup. Makes future stages insertable but stays simple.

---

## 18. MEMORY MANAGEMENT

- Decode **incrementally** (PyAV generator) — never materialize the whole video.
- Hold **one `FrameView`** (raw frame + at most one cached ndarray) at a time; drop it immediately after `process()`. Optional tiny bounded look-back buffer (default size 1).
- **NumPy array lifecycle:** an `rgb24` frame is ~`W×H×3` bytes (≈6.2 MB at 1080p). At most **one converted array exists at a time** (cached in the current `FrameView`, released when the view is dropped). Un-sampled frames are **never** converted, so EVERY_N/TARGET_FPS reduce both CPU *and* peak array memory. No list/array accumulation across frames.
- **No** accumulation of frame arrays; **no** per-frame DB rows; **no** per-frame disk writes.
- Explicit `del view` / rely on refcount; periodic `gc.collect()` only if a leak is observed.
- **Acceptance criterion:** processing a long clip shows **flat, bounded RSS** independent of video length/frame count, for both metadata-only (NoOp) and full-conversion runs (measured with `psutil` — §36/§39).

---

## 19. PROGRESS REPORTING

Durable bounded progress on the single session row: `frames_decoded, frames_processed, current_frame_index, current_pts_seconds, progress_percent, decode_fps, processing_fps, last_heartbeat_at`.

**Update strategy (throttled):** persist **every `CV_PROGRESS_INTERVAL_SECONDS` (default 2s) OR every `CV_PROGRESS_EVERY_N_FRAMES` (default 100) frames, whichever first**, plus a **forced final update** on terminal state. **No per-frame DB writes.**

**Unknown/unreliable total:** `frames_total_estimate` from `VideoAsset.frame_count` if present and plausible, else `round(duration_s * fps)`, else `null`. When null/untrusted → `progress_percent = null` and the UI shows *frames processed + current timestamp* instead of a bar (never a fabricated percentage).

---

## 20. REAL-TIME PROGRESS EVENTS → see D6

**Recommendation: DB-authoritative progress + a thin WebSocket overlay reusing existing Channels, with REST polling as the guaranteed fallback.** The frozen architecture (§10/§18) mandates Redis pub/sub → Channels → WS, and the infra already exists (`channels_redis` layer configured, JWT WS auth, `SystemConsumer`, `group_send` pattern). The CV runtime publishes lightweight progress to Redis `live:session:{id}`; a Channels consumer relays to a per-session WS group. **DB remains the source of truth**; WS is lossy/best-effort. If WS proves noisy in implementation, the REST poll of `GET /processing-sessions/{id}` (already bounded) fully suffices — so WS is *additive*, not load-bearing.

---

## 21. CANCELLATION (real)

- User/API → Django sets `requested_action=CANCEL` (+ `cancel_requested_at`) and publishes on the command bus. **Durable flag in Postgres is authoritative**; Redis publish is the fast path.
- Runtime checks `requested_action` at **every safe frame boundary** (between frames) — bounded latency.
- On CANCEL: break the loop → `finally` closes `VideoSource`, releases GPU reservation → `transition(→CANCELLED)`.
- Per state:
  - **CREATED/QUEUED:** Django transitions directly `→CANCELLED` (runtime hasn't claimed it; guarded against a claim race by `SELECT FOR UPDATE`).
  - **INITIALIZING/RUNNING/PAUSED:** runtime performs it at the next boundary.
- **STOP** = graceful terminal (`→STOPPED`) distinct from CANCEL (user abort) — both real, both close resources.
- **Acceptable latency:** ≤ one frame-processing interval (sub-second for no-op; documented). Cancellation is never reported successful while the loop still runs.

---

## 22. FAILURE HANDLING (stable codes, sanitized messages)

| Condition | `error_code` | Behavior |
|---|---|---|
| Video row missing | `video_missing` | FAIL at INITIALIZING |
| StoredArtifact missing | `artifact_missing` | FAIL |
| Storage file missing on disk | `storage_file_missing` | FAIL |
| Snapshot capture failure (creation) | `snapshot_failed` | reject creation (400) — no session persisted |
| Invalid/again-unreadable snapshot | `snapshot_invalid` | FAIL |
| Decoder unavailable (`av` import) | `decoder_unavailable` | FAIL (reuses probe code) |
| Decoder open failure | `decoder_open_failed` | FAIL |
| Mid-stream corrupt frame | `corrupt_frame` (per-frame, counted) → `corrupt_source` if unreadable | skip+count; FAIL only if stream unusable |
| Runtime crash | (set by watchdog) `heartbeat_lost` | §23 |
| Worker/process termination | `heartbeat_lost` | §23 |
| Redis unavailable | `redis_unavailable` | commands/live degrade; DB still authoritative; retry w/ backoff, else FAIL (recoverable) |
| PostgreSQL unavailable | `db_unavailable` | pause durable writes, bounded retry/backoff, else FAIL(recoverable) |
| Progress persistence failure | `progress_persist_failed` | best-effort; escalate only if persistent |
| Cancellation race | (no error) | idempotent; last legal transition wins |
| Invalid state transition | `invalid_transition` | rejected + logged, no state change |
| GPU unavailable | (not fatal Phase 5) | fall back to CPU, tag session |
| Insufficient GPU memory (future) | `gpu_oom` | reserved code, Phase 6 |

All `error_message` values are **sanitized** (no absolute paths, no secrets) — reuse audit's redaction posture. Storage paths are internal-only (`resolve_path` doc-string already warns).

---

## 23. HEARTBEATS & STALE SESSION RECOVERY

- **Runtime heartbeat:** Redis key `session:{id}:heartbeat` = timestamp, TTL `CV_HEARTBEAT_TTL_SECONDS` (default 30s), refreshed each progress tick; plus DB `last_heartbeat_at` mirror.
- **Watchdog:** new **Celery-beat** task `apps.processing.tasks.reconcile_stale_sessions` (e.g., every 60s) finds `state ∈ {INITIALIZING,RUNNING,PAUSING,PAUSED,RESUMING}` whose heartbeat (Redis missing/expired **and** DB `last_heartbeat_at` older than threshold) → `transition(→FAILED, reason=heartbeat_lost)`.
- **Conservative policy (Phase 5):** stale → **FAILED** (manual retry), **not** auto-requeue. Idempotent resume-from-checkpoint is a frozen Phase-6+ concern (measurements keyed by frame index) — Phase 5 has no measurements, so auto-rerun risk (duplicate side effects) is avoided by not auto-retrying.
- Distinct from the existing **general Celery worker heartbeat** (`celery:worker:heartbeat`) — per-session liveness is a separate key namespace.

---

## 24. RETRY & IDEMPOTENCY → see D7

**Recommendation: retry = a NEW session** (`state=CREATED`) with `retry_of=<original>`, `retry_count=original.retry_count+1`, reusing the same (deduped) snapshot + params. The original **stays immutable as execution history** (FAILED/CANCELLED/STOPPED are terminal, never reset). Preserves auditability; avoids losing why a run failed. **Duplicate concurrent execution prevented** by (a) the atomic `FOR UPDATE SKIP LOCKED` claim, (b) the partial-unique concurrency index (§25), and (c) duplicate-active guard at creation (§30). Only terminal sessions may be retried.

---

## 25. CONCURRENCY → see D8

**Recommendation: default one active processing session** (`CV_MAX_CONCURRENT_SESSIONS=1`, configurable). Enforced **in the runtime + DB**, not the frontend:
- Atomic claim: `SELECT … FROM processing_session WHERE state='QUEUED' ORDER BY queued_at FOR UPDATE SKIP LOCKED LIMIT (capacity - active)`.
- **Partial unique index** (when limit=1) guaranteeing at most one row in non-terminal *active* states, as a hard backstop.
Bound by CPU/RAM/disk-I/O now and future GPU VRAM later. No premature multi-GPU optimization.

---

## 26. STORAGE & RETENTION SAFETY

Wire the **existing** reserved hook `apps/ingestion/retention_handlers.py::_video_is_protected(asset)`:
```python
return ProcessingSession.objects.filter(
    video_asset=asset, state__in=NON_TERMINAL_STATES
).exists()
```
so `RawVideoRetentionHandler.purge` **skips** any VideoAsset bound to a non-terminal session (already loops with a `_video_is_protected` guard). VideoAsset FK is `PROTECT` from the session, so a hard-delete attempt would also raise — defense in depth. **Phase 5 produces minimal durable output** (session row + snapshot + metrics/logs); **no decoded frames persisted**. Future processing outputs (detection/track metadata) get their own retention tiers in Phase 6 (`DataCategory` already has `DETECTION_METADATA/TRACK_METADATA` reserved).

---

## 27. AUDIT INTEGRATION

Add `EventType` values (audit app): `PROCESSING_REQUESTED, PROCESSING_QUEUED, PROCESSING_STARTED, PROCESSING_PAUSED, PROCESSING_RESUMED, PROCESSING_CANCEL_REQUESTED, PROCESSING_CANCELLED, PROCESSING_STOPPED, PROCESSING_COMPLETED, PROCESSING_FAILED, PROCESSING_RETRY_REQUESTED`. Emit via `record_audit(event_type, action, target_type="ProcessingSession", target_id=<id>, metadata={...})`, `source="celery"|"cv_runtime"|"django"` as appropriate. **Bounded metadata only:** `session_id, video_id, snapshot_hash, outcome, error_code, frames_processed, duration_s`. **Never** snapshot geometry arrays or per-frame data. State transitions each write one audit event (frozen §13).

---

## 28. OBSERVABILITY

Extend the strict allowlist (`collectors.ALLOWED.update({...})`, ingestion pattern) with **counters/summaries only, no high-cardinality labels**:
- `processing_sessions_requested_total` (counter)
- `processing_sessions_finished_total{outcome}` — outcome ∈ {completed,failed,cancelled,stopped} (bounded label)
- `processing_session_duration_ms` (summary)
- `processing_decode_fps` (summary), `processing_throughput_fps` (summary)
- `cv_runtime_heartbeat_age_seconds` (summary, from watchdog)

**Forbidden as labels:** session_id, video_id, user_id (cardinality) — per-session detail lives on the `ProcessingSession` row and API. **Active sessions** = a DB count query exposed via API, not a metric label.

---

## 29. LOGGING

Structured (structlog) CV-runtime logs bind: `request_id` (where applicable), `session_id`, `runtime_id`, `state_from→state_to`, `error_code`, `frames_processed`. **Never log:** raw frame data, full snapshot geometry, secrets, or absolute storage paths in normal logs. **Frame-loop volume control:** no per-frame log at INFO; a throttled progress log at the same cadence as progress persistence; per-frame detail only under an explicit DEBUG flag `CV_LOG_FRAMES=false` default.

---

## 30. API DESIGN

Follow existing unversioned `/api/` convention (frontend `videoApi` uses `/videos`); session is a first-class resource:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/processing-sessions` | create (+capture snapshot); body `{video_id, sampling, processor, device_preference}` |
| GET | `/api/processing-sessions` | list; filter `?video=&status=&camera=`; **paginated** (existing pagination) |
| GET | `/api/processing-sessions/{id}` | detail (progress, snapshot_hash, error) |
| POST | `/api/processing-sessions/{id}/cancel` | set `requested_action=CANCEL` |
| POST | `/api/processing-sessions/{id}/stop` | set `requested_action=STOP` |
| POST | `/api/processing-sessions/{id}/pause` | set `requested_action=PAUSE` |
| POST | `/api/processing-sessions/{id}/resume` | set `requested_action=RESUME` |
| POST | `/api/processing-sessions/{id}/retry` | create linked new session |
| GET | `/api/processing-sessions/{id}/snapshot` | snapshot metadata (hash, schema version, entity revisions) — not raw geometry dump by default |

**Chosen contract:** `POST /api/processing-sessions` with `video_id` (cleaner REST than nesting under the video). **Validation:** video must exist + `validation_status=VALID` + active; params serializer rejects unknown keys. **Idempotency / duplicate-active prevention:** reject (409) if the video already has a non-terminal session (configurable). **Command endpoints** only set `requested_action` — they never write `state`. **Never expose Celery/runtime task ids**; the session UUID is the identity.

---

## 31. PERMISSION MATRIX (recommended)

Roles: `system_admin, traffic_admin, traffic_operator, traffic_analyst, incident_operator, viewer` (from `apps/common/roles.py`). Enforced **server-side** via `HasAnyRole` subclasses.

| Action | system_admin | traffic_admin | traffic_operator | traffic_analyst | incident_operator | viewer |
|---|---|---|---|---|---|---|
| Create/start processing | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Pause/Resume/Stop/Cancel | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Retry | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View session list/detail | ✅ | ✅ | ✅ | ✅ (read) | ❌ | ❌ |
| View snapshot metadata | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |

**Rationale:** operators/admins run/control processing; analysts read completed sessions (analysis role); **viewer excluded** from raw-video processing resources (privacy — raw video, frozen §32); `incident_operator` is an alert-lifecycle role (Phase 9+), no Phase-5 processing access. Mirrors the existing video-permission posture (operator ingests/processes; viewer excluded).

---

## 32. FRONTEND SCOPE

Next.js App Router (existing `/admin` area, Tailwind, `apiFetch`, `useAuth`). Add:
- `lib/processingApi.ts` (typed client) + `ProcessingSession` type.
- **Start Processing** action on `/admin/videos/[id]` (only when `validation_status=VALID`; role-gated) with sampling/processor form.
- `/admin/processing` — **session list** (video, status badge, progress, created, snapshot hash short).
- `/admin/processing/[id]` — **detail**: status, progress (frames processed, current source timestamp, processing FPS), runtime status, snapshot hash + basic metadata, **Cancel/Stop/Pause/Resume/Retry** buttons (role/state-gated). Progress via REST poll (+ optional WS overlay, §20).
- Sidebar link under Media/Processing (role-gated like Videos).

**Explicitly NOT built:** bounding boxes, detection overlays, tracking trails, counts, AI results, live camera, RTSP, analytics. UI copy must state clearly: *"Phase 5 validates processing infrastructure; no AI detection is performed."*

---

## 33. HEALTH & READINESS

- **Do NOT** make `/api/readyz` fail when the CV runtime is offline — the API/ingestion/config remain fully usable without it. Keep `readyz` checks = {database, redis, celery} (unchanged).
- Add a **separate, non-gating** signal: `GET /api/processing/runtime-status` → `{cv_runtime_available, heartbeat_age, gpu_status}` (reads a `cv:runtime:heartbeat` Redis key the runtime writes, mirroring the celery-heartbeat pattern in `health/views.py`).
- **Processing-request semantics when runtime offline:** creation still succeeds (durable `QUEUED`); the session waits. The API response + UI **surface** that no runtime is currently available (no silent hang, no false "started"). This matches frozen "Django crashes / runtime continues" resilience symmetry.

---

## 34. WINDOWS-FIRST RUNTIME

- **Startup script** `scripts/dev_cv_runtime.ps1` → `& .\.venv\Scripts\python.exe manage.py run_cv_runtime` (paths quoted — repo path `E:\ai camera` contains a space; `resolve_path` already guards traversal).
- **Graceful shutdown:** SIGINT/SIGBREAK (Ctrl+C) handler sets a shutdown flag → finish current frame → close `VideoSource` → release GPU reservation + heartbeat key → exit 0. In-flight session left in a safe non-corrupt state (RUNNING with fresh checkpoint; watchdog will FAIL it if the process is gone).
- **File-handle release:** PyAV `container.close()` in `finally` (Windows locks files); temp handles closed before rename (existing ingestion pattern already does this).
- **Celery `solo` pool** (existing Windows constraint) affects only the watchdog task — fine (short job).
- **Process/claim locks:** the DB `FOR UPDATE SKIP LOCKED` claim + heartbeat means a **stale lock after a crash self-heals** (row stays QUEUED/gets FAILED by watchdog; no OS-level lock file). Optional Redis `cv:runtime:{id}` presence key with TTL.

---

## 35. GPU-LESS OPERATION

Phase 5 has no model → the foundation **must** run without a GPU. The manager reports `{available:false, mode:"cpu"}` cleanly; NoOp/FrameCount processors run CPU-only. **Acceptance does not depend on CUDA.** The GPU abstraction merely *prepares* Phase 6 (device selection, reservation, VRAM interface) without blocking Phase 5. (This laptop *has* an RTX 3070 + driver + nvidia-smi, so the "GPU present" path is also testable — but not required.)

---

## 36. PERFORMANCE VALIDATION

Benchmarks to run during implementation (baseline, not targets):
- Videos: small (existing 217 KB clip), medium (720p ~15 s), longer (1080p ~60 s if practical) — plus at least **one real H.264 traffic clip** for a realistic (non-`testsrc`) number.
- Modes: EVERY_FRAME, EVERY_N=5, TARGET_FPS.
- Measure: wall-clock, decode FPS, processed FPS, **peak RSS (psutil)**, progress-update count.

**Required NumPy benchmark matrix** (four variants; quantifies the lazy-conversion payoff and validates the single-cached-copy contract):
| # | Variant | Purpose | Status |
|---|---|---|---|
| 1 | **decode only** (no pixel access) | raw decode ceiling | ✅ measured §1.8 (1080p ≈ 1865 fps) |
| 2 | **decode + PyAV RGB convert, no NumPy** (`reformat('rgb24')` + plane bytes) | swscale cost without ndarray alloc | ✅ measured §1.8 (1080p ≈ 265 fps) |
| 3 | **decode + `frame.to_ndarray(format="rgb24")`** every frame | canonical-path cost incl. ndarray alloc | ⏳ **deferred** (needs NumPy installed — first implementation step) |
| 4 | **EVERY_N=5 + `to_ndarray` only for accepted frames** | proves sampling-before-conversion savings | ⏳ **deferred** (expected ≈ variant-1 decode with 1/5 of variant-3 convert cost) |

Variants 3–4 cannot run during planning (NumPy must not be installed now, req. 11); they run as the **first implementation step** after NumPy is pinned/installed, recorded in the verification report. Variant 2 is a valid numpy-free proxy establishing that the swscale copy — not ndarray allocation — dominates conversion cost.
- Record results in the Phase 5 verification report. **No unrealistic targets pre-measurement.** Established upper-bound today (§1.8): 1080p decode+convert ≈ 265 fps; real footage will be lower but decode remains non-bottleneck.

---

## 37. REPOSITORY CHANGES EXPECTED

**New:** `apps/processing/` (models, services/state.py, serializers, views, urls, permissions, tasks.py [watchdog], runtime/{loop,pipeline,gpu,video_source,sampler,frame_meta,processors/}, management/commands/run_cv_runtime.py, retention/audit/observability wiring, migrations/0001_initial.py). Frontend `lib/processingApi.ts`, `app/admin/processing/{page,[id]/page}.tsx`, video-detail Start action. `scripts/dev_cv_runtime.ps1`. ADRs 024–027. `PHASE_5_VERIFICATION_REPORT.md`.
**Edited (additive, non-breaking):** `apps/ingestion/retention_handlers.py` (`_video_is_protected` body), `apps/audit/models.py` (EventType additions → one trivial migration), `config/celery.py` (watchdog beat entry), `config/settings/base.py` (CV_* settings), `config/urls.py` (route include), `requirements/base.txt` (**`numpy==2.2.6`** — runtime), `requirements/dev.txt` (psutil, dev-only). No historical migration edits.

---

## 38. MODELS / MIGRATIONS EXPECTED

- `apps/processing/migrations/0001_initial.py` — `ProcessingConfigSnapshot`, `ProcessingSession` (+ indexes, CheckConstraint, partial unique index).
- `apps/audit/migrations/0003_*` — EventType choices (harmless `AlterField`; or avoid entirely by using string constants — see §41).
- Chain remains 12 → 13(+1) migrations; clean from empty DB; `aitraffic_app` (non-superuser) applies all; no superuser-only DDL (partial index + check constraints are standard). **Working dev data preserved** (purely additive).

---

## 39. DEPENDENCIES

| Name | Version | Purpose | License | Windows | Necessary in P5? |
|---|---|---|---|---|---|
| **PyAV** | 13.1.0 (existing) | full processing decoder | bundled-FFmpeg (**license review before commercial redistribution** — ADR-023) | ✅ verified | Reuse — **no change** |
| **NumPy** | **`numpy==2.2.6`** (latest 2.2.x); conservative fallback **`numpy==1.26.4`** | **canonical in-memory frame representation** (`rgb24` ndarray) — backs `av.VideoFrame.to_ndarray()`; stable array contract for Phase 6 detectors | **BSD-3-Clause** | ✅ (cp312 wheels) | **YES — Phase 5 runtime dep** → `requirements/base.txt` |
| **psutil** | latest | memory acceptance tests only | BSD-3-Clause | ✅ | **dev.txt only** (§18/§36) |

**NumPy — full dependency review (revised: Phase 5 runtime dependency).**
- **Why now, not Phase 6:** `rgb24` ndarray is the correct standard in-memory frame representation for the CV pipeline. Fixing it in Phase 5 gives Phase 6 a stable array contract (`FrameView.as_rgb_ndarray()`, §16) so a detector drops in with **no breaking pipeline redesign**. `frame.to_ndarray()` *requires* numpy at call time (confirmed live: raised `ModuleNotFoundError` in the numpy-free venv). NumPy itself is **not an AI dependency** — it is the array primitive underneath PyAV's own API.
- **Version compatibility (req. 9):** pinned **`numpy==2.2.6`**.
  - **Python 3.12.9:** numpy 1.26.x and 2.0–2.2.x all ship cp312 wheels. ✅
  - **PyAV 13.1.0:** NumPy 2.x support landed in the PyAV v12 series; **13.1.0 works with both numpy 1.26 and 2.x**. ✅
  - No other project dep constrains numpy (torch/opencv absent). **Fallback `numpy==1.26.4`** only if a future transitive tool needs the 1.x ABI.
- **License & commercial compatibility (req. 10):** **BSD-3-Clause** — permissive, commercially friendly, no copyleft, no redistribution restriction. Compatible with commercial use. (Contrast: the PyAV-bundled FFmpeg still needs the separate license review of ADR-023; numpy adds **no** new licensing risk.)
- **Install discipline (req. 11):** pinned in this plan; **NOT installed during planning.** Installed as the **first implementation step**, which also unblocks benchmark variants 3–4 (§36).

**No AI dependencies in Phase 5 (req. 12).** Explicitly **NOT** added: PyTorch, TensorFlow, Ultralytics, OpenMMLab, OpenCV, pretrained weights, CUDA toolkit. NumPy is a numeric-array primitive, not an AI framework. GPU detection uses `nvidia-smi` (already on the machine) — no library. **Nothing downloaded at runtime.**

---

## 40. ADRs (next = ADR-024)

Create only what ships:
- **ADR-024 — Processing Session Architecture & State Machine** (states, single-writer, `requested_action`, idempotency, terminal semantics; realizes the "ADR-003" concept from Phase 0 under the actual numbering).
- **ADR-025 — CV Runtime Boundary** (standalone process, Postgres+Redis comms, no HTTP, claim protocol, Windows startup/shutdown — D1).
- **ADR-026 — Immutable Processing Configuration Snapshot** (contents, canonical hash, capture boundary, dedup — D2/D3).
- **ADR-027 — GPU Resource Management** (framework-independent detection, nvidia-smi optional, reservation, CPU fallback, single-session default, multi-GPU interface-only — D9).

Written **during implementation** to describe what actually ships (repo convention: ADRs are Accepted alongside their phase, not drafted in planning).

---

## 41. MIGRATION STRATEGY

Additive only. `0001_initial` for the processing app. For audit EventType, **prefer adding module-level string constants** consumed by `record_audit(event_type=...)` (which takes `str`) to avoid touching `audit/models.py` at all; if enum membership is desired, a single trivial `AlterField(choices=...)` migration (no data change). Verify: `migrate` from empty DB green; `aitraffic_app` role sufficient (no superuser); Phase 0→5 chain intact; no historical migration rewritten.

---

## 42. IMPLEMENTATION ORDER (dependency-aware)

1. Confirm Phase 4 baseline (done: 188/91%). 2. Lock frozen scope (done). 3. Real-clip PyAV benchmark. 4. Confirm GPU/env facts (done). 5. Finalize ProcessingSession model + state machine (ADR-024). 6. Snapshot model + capture service (ADR-026). 7. CV runtime boundary + claim protocol (ADR-025). 8. GPU manager skeleton (ADR-027). 9. `VideoSource`/`LocalFileSource` over PyAV. 10. `FrameMeta` + timestamps. 11. Sampler (3 modes). 12. `FrameProcessor` + NoOp/FrameCount. 13. Pipeline orchestrator. 14. Bounded progress. 15. Cancellation/pause/resume/stop. 16. Heartbeats + watchdog + stale recovery. 17. Retention hook wiring. 18. Audit + observability + logging. 19. APIs + permissions. 20. `run_cv_runtime` command + `dev_cv_runtime.ps1`. 21. Frontend. 22. Tests incrementally (§37). 23. Failure tests. 24. Perf benchmarks. 25. Full regression (188 + new). 26. Clean-migration verify. 27. Windows manual runtime verify. 28. Verification report.

---

## 43. TESTING STRATEGY

**ProcessingSession:** creation (valid); reject invalid/archived/non-VALID video; every allowed transition; every forbidden transition rejected; terminal immutability; duplicate-active prevention. **Snapshot:** creation; deterministic canonicalization; hash determinism; immutability (save-guard); schema version; correct config captured (camera/lanes/rois/lines revisions+geometry); irrelevant data excluded; **no secrets**; **post-capture config edit does not alter stored snapshot**; dedup reuse by hash. **Decoder/VideoSource:** full sequential iteration; frame identity/index; PTS/time_base; VFR fixture (best-effort via crafted timestamps); corrupt-midstream skip+count; `close()` cleanup. **Sampling:** every-frame, every-N, target-fps determinism; source identity preserved. **Pipeline:** full successful run; NoOp; FrameCount; **assert no detection-like output exists**. **FrameView/NumPy boundary:** `NoOpFrameProcessor` processes a run **without any `to_ndarray` call** (assert via spy/counter — proves conversion is not automatic); `as_rgb_ndarray()` returns canonical `rgb24` shape `(H,W,3)` `uint8` C-contiguous matching source dims; **conversion is cached** (two calls → same object, one `to_ndarray`); un-sampled frames are **never converted** (EVERY_N: convert count == processed count, not decoded count); alternate-format escape hatch caches per-format. **Progress:** bounded update count (assert ≤ ceil), forced final, unknown-frame-count → null percent. **Cancellation:** queued-cancel, running-cancel actually stops (assert loop exits), cleanup; pause/resume; stop. **Runtime:** heartbeat written; worker-loss → watchdog FAILED; duplicate-execution prevention (concurrent claim). **GPU manager:** CPU-only path; GPU-present path (this laptop) parses nvidia-smi; GPU-unavailable path (simulate missing binary); reserve/release; **no fake device**. **Permissions:** start/read/cancel/retry per role; viewer excluded (403). **Retention:** active session protects source video (purge skips; hard-delete blocked by PROTECT). **Regression:** all **188** existing tests remain green; none removed/weakened.

Deterministic fixtures via existing `tests/_video_fixtures.make_test_video` (PyAV testsrc — no new assets, no numpy).

---

## 44. FAILURE TESTING (explicit)

Missing video file; missing StoredArtifact; decoder unavailable (monkeypatch import); decoder open failure (truncated file); corrupt mid-stream frame; runtime crash (simulate no heartbeat); heartbeat loss → watchdog; DB unavailable (where practical / mocked); Redis unavailable (commands degrade, DB authoritative); cancellation race (cancel exactly at claim); double dispatch (two claimers, one wins); duplicate runtime claim; snapshot capture failure; storage read failure; GPU detection failure (nvidia-smi missing/garbage output → CPU, not crash); runtime shutdown mid-processing (Ctrl+C → safe state). **No failure is masked as fake successful completion.**

---

## 45. SECURITY

Server-side permission enforcement on every endpoint + command (frozen §32; `viewer` excluded from raw-video processing). Sanitized errors (no paths/secrets). Snapshot excludes PII/secrets. Audit every session lifecycle event. Storage `resolve_path` internal-only (never returned via API). No new external surface; CV runtime serves no HTTP. Reuse JWT/roles. Raw video = privacy-sensitive T1 (frozen retention).

---

## 46. PERFORMANCE

Baseline established today (§1.8/§36); real-clip numbers recorded in the verification report. Bounded progress writes (≤ every 2 s / 100 frames). Bounded memory (flat RSS, §18). Bounded metrics cardinality (§28). Decode is not the bottleneck; Phase 5 imposes negligible CPU beyond decode + optional pixel touch.

---

## 47. MIGRATION STRATEGY (verification)

`python manage.py migrate` from empty DB → green under `aitraffic_app`; `makemigrations --check` clean; Phase 0→5 chain intact; dev data preserved; no superuser DDL. (Same content as §38/§41 — verified in the report.)

---

## 48. ACCEPTANCE CRITERIA

All 188 existing tests green; frozen Phase 5 scope honored; **no AI detection/model/API introduced**; no RTSP/CCTV/webcam; no vehicle detection/tracking/counting. State machine enforced through one service layer with DB guards. Immutable snapshot implemented, deterministic, immutable, config edits don't alter history. Valid VideoAsset processes end-to-end frame-by-frame. Full sequential decode works; source frame identity preserved; PTS-based timestamps used where available. EVERY_FRAME + EVERY_N + TARGET_FPS work. No full-video RAM load; no per-frame DB writes; bounded progress. **Canonical frame representation is NumPy `rgb24` ndarray, converted lazily and only for sampled frames; NoOp runs without conversion; conversion is cached (no duplicate copies); un-sampled frames are never converted; peak RSS flat regardless of length.** Cancellation actually stops active processing; pause/resume/stop work. Heartbeat implemented; stale sessions recovered conservatively (→FAILED); duplicate concurrent execution prevented. Source video protected during active processing. Runtime works CPU-only; GPU manager reports the **real** environment (RTX 3070 / CPU) with no fake device. Audit + bounded observability + structured logging integrated. Permissions enforced server-side. Frontend session workflow works (start/list/detail/cancel/retry). Clean migration passes; full suite passes; Windows runtime manually verified. **No external AI model/API; no live camera; no detection/tracking.** No mandatory criterion may fail.

---

## 49. VERIFICATION PROCEDURE

1. `backend/.venv` Python 3.12.9 confirmed active (guard against global 3.14). 2. `pytest --cov=apps` → ≥188 passing incl. new tests, coverage not regressed. 3. `ruff check` clean. 4. Frontend `tsc --noEmit` + production build clean. 5. Clean migrate from empty DB under `aitraffic_app`; `makemigrations --check` clean. 6. Manual Windows E2E: start CV runtime, upload/select a valid video, POST session, observe QUEUED→…→COMPLETED, verify snapshot hash, progress, audit events, metrics; test cancel/pause/resume/retry; kill runtime mid-run → watchdog FAILED; verify retention skips active session; verify CPU-only and GPU-present detection. 7. Record perf baseline (real clip). 8. Produce `PHASE_5_VERIFICATION_REPORT.md` with actual numbers.

---

## 50. KNOWN RISKS

1. **Interpreter drift (env).** Global Python 3.14 + torch cu128 shadows the project venv in a naive shell; running `manage.py` under 3.14 fails (no structlog). *Mitigation:* all scripts pin `.venv`; add a runtime interpreter-version guard; document in README. (Do not repair during planning.)
2. **Bundled-FFmpeg licensing** (ADR-023) — review before commercial redistribution; not a Phase 5 blocker. *Mitigation path:* LGPL-only FFmpeg / external ffprobe.
3. **Windows file-handle locks / graceful Ctrl+C** — mitigated by `finally: close()`, SIGBREAK handling, DB-claim self-healing.
4. **Single-writer discipline** — risk if any view writes `state`; mitigated by the single `transition()` service + DB constraints + tests.
5. **Synthetic-benchmark optimism** — real H.264 slower; mitigated by a mandatory real-clip benchmark before freezing numbers.
6. **Heartbeat/watchdog false positives** under GC/IO stall — mitigated by TTL headroom (30 s) + DB mirror + conservative FAILED (no auto-rerun).
7. **Scope creep toward detection** — mitigated by explicit non-goals + a test asserting no detection output.
8. **`requested_action` vs DB-state race** — mitigated by treating Postgres as authoritative and Redis as fast-path only.

---

## 51. ESTIMATED EFFORT

Frozen Phase 0 estimate (§"5 Session engine + CV runtime + GPU"): **optimistic 7 d / likely 12 d / pessimistic 20 d.** My assessment given the mature, well-factored foundation (reusable audit/retention/observability/Channels/storage, ready retention hook, verified decoder): **~12–15 developer-days likely**, front-loaded on the state machine + runtime boundary + snapshot (ADR-024/025/026) and the failure/heartbeat test matrix; GPU manager and frontend are comparatively light. Add ~1–2 d contingency for Windows runtime-lifecycle hardening.

---

## Decisions Recommended for Approval

### D1 — Processing Runtime: **Standalone CV runtime process (Option B)**
- **Options:** A dedicated Celery queue/worker; **B standalone CV runtime process**; C hybrid (Celery dispatch + CV runtime).
- **Recommendation: B.**
- **Rationale:** Frozen ADR-002/§10 mandate a dedicated CV runtime and explicitly *reject* CV-in-Celery (line 670). Django writes QUEUED + publishes a command; the runtime is the single state writer. Celery beat is retained only for the watchdog (legit scheduled maintenance).
- **Tradeoffs:** More setup than a Celery task (a management command + claim loop), but preserves the frozen Postgres+Redis boundary and single-owner GPU model.
- **Future consequence:** Phase 6 adds detection/GPU model loading **inside the same process** with no re-architecture; the runtime can later move hosts unchanged.

### D2 — Snapshot Capture: **At ProcessingSession creation (Option A)**
- **Options:** A creation; B at QUEUED; C at processing start.
- **Recommendation: A** (synchronous, in the creation transaction).
- **Rationale:** Binds config identity to the user's intent at request time (what they saw when clicking "process"); creation is a Django control-plane action that can read config models cleanly (keeps CV runtime out of config internals); satisfies ADR-021's "snapshot at session start." Immutability is precisely the protection against later config edits.
- **Tradeoffs:** Config could change between creation and execution — but that's the *desired* freeze, not a bug. Rejected C because Phase 5 has no replay and "latest config at start" would decouple the run from the request.
- **Future consequence:** Enables a future "process against snapshot X" without redesign.

### D3 — Snapshot Storage: **Content-hash deduplication**
- **Options:** one snapshot row per session; **dedup by `snapshot_hash`**.
- **Recommendation: dedup** (`get_or_create` by canonical hash; session FK→snapshot PROTECT).
- **Rationale:** Reuses existing `canonical_hash`; bounded storage; multiple runs of the same config share one immutable row → easier "did config change between runs" queries. Immutability makes sharing safe.
- **Tradeoffs:** Marginally more logic than 1:1; a shared row must never be mutated (guaranteed by the immutability guard). 1:1 remains an acceptable simpler fallback if review prefers it.
- **Future consequence:** Natural basis for snapshot-addressed reprocessing.

### D4 — Decoder: **Continue with PyAV 13.1.0**
- **Options:** PyAV; switch to OpenCV/ffprobe.
- **Recommendation: PyAV** via a `VideoSource` abstraction.
- **Rationale:** Benchmark-verified sequential decode, reliable PTS/time_base, CFR/VFR handling, Windows-clean, bundled libav, decode is not the bottleneck; reuses Phase 4 investment (ADR-023 "same tool Phase 5 builds on"). Pairs with NumPy for the canonical `rgb24` array (D10).
- **Tradeoffs:** FFmpeg licensing review pending (documented). OpenCV/ffprobe stay as documented fallbacks only.
- **Future consequence:** `VideoSource` Protocol lets Phase 6 add SimulatedStream/RTSP sources without touching the pipeline.
- **D4-note (NumPy) — see D10.**

### D10 — NumPy: **Phase 5 runtime dependency (canonical `rgb24` ndarray, lazy conversion)** *(revised per correction)*
- **Options:** (A) defer numpy to Phase 6; (B) **adopt numpy now as the canonical in-memory frame representation with lazy, sampled-only conversion.**
- **Recommendation: B** — pin **`numpy==2.2.6`** (fallback `1.26.4`) in `requirements/base.txt`.
- **Rationale:** `rgb24` ndarray is the correct standard CV frame representation and the format `to_ndarray()` produces; fixing it in Phase 5 gives Phase 6 a **stable array contract** (`FrameView.as_rgb_ndarray()`) so a detector drops in with **no breaking pipeline redesign**. NumPy is a numeric-array primitive (BSD-3, commercial-friendly), **not** an AI framework — adopting it does not violate the no-AI boundary. Conversion stays **lazy**: raw frames decoded, **sampled before conversion**, ndarray materialized only when a processor asks and only for accepted frames, cached once (no duplicate copies).
- **Tradeoffs:** one runtime dep added vs. a numpy-free Phase 5. Accepted: the alternative (numpy-free now, add later) would force a `FrameProcessor` signature/return change in Phase 6 — exactly the breaking redesign this correction avoids.
- **Guardrails:** requirements 1–6 enforced by the `FrameView` design (§16) and asserted by tests (§43); benchmark variants 3–4 (§36) run once numpy is installed (first implementation step; **not installed during planning**). No PyTorch/TF/Ultralytics/OpenCV/weights (req. 12).

### D5 — Sampling: **Ship EVERY_FRAME + EVERY_N + TARGET_FPS**
- **Recommendation: all three.**
- **Rationale:** Cheap; TARGET_FPS (PTS-based, VFR-safe) is the realistic basis for future detection stride; all deterministic and preserve source identity.
- **Tradeoffs:** Slightly more test surface (covered in §43). No downside on cost.
- **Future consequence:** Phase 6 detection-stride maps directly onto TARGET_FPS/EVERY_N.

### D6 — Progress Delivery: **DB-authoritative + thin WebSocket overlay, REST-poll fallback**
- **Options:** polling only; WebSocket events; hybrid.
- **Recommendation: hybrid** (DB truth; runtime→Redis→Channels WS overlay; REST poll guaranteed fallback).
- **Rationale:** Frozen §10/§18 mandate Redis pub/sub → Channels → WS and the infra already exists; WS is additive and lossy; the DB row is the source of truth.
- **Tradeoffs:** Small relay-consumer complexity; if noisy, REST polling alone suffices (WS is not load-bearing).
- **Future consequence:** Same channel carries live measurements/twin overlays in later phases.

### D7 — Retry Model: **New session per retry, linked via `retry_of`**
- **Options:** reuse/reset the failed session; **new linked session**.
- **Recommendation: new session** (original immutable terminal history).
- **Rationale:** Preserves auditability and failure forensics; avoids resurrecting terminal state; duplicate execution prevented by atomic claim + concurrency index + duplicate-active guard.
- **Tradeoffs:** More session rows over time (cheap, bounded).
- **Future consequence:** Clean lineage for future resume-from-checkpoint semantics.

### D8 — Default Concurrency: **One active session (configurable)**
- **Recommendation: `CV_MAX_CONCURRENT_SESSIONS=1`**, enforced in runtime + DB (partial unique index + `FOR UPDATE SKIP LOCKED`).
- **Rationale:** Frozen §14 single-model/single-session on 8 GB; correctness over throughput on one laptop.
- **Tradeoffs:** Serializes work now; configurability leaves headroom.
- **Future consequence:** Multi-session/multi-GPU is a config + scheduler change, not a redesign.

### D9 — GPU Manager: **Lightweight, framework-independent detection (nvidia-smi optional), CPU-first**
- **Recommendation:** detect via `nvidia-smi` (present on this machine) with clean CPU fallback; record identity + VRAM; logical reserve/release (Redis + in-process); device selection + VRAM-budget interface stub; **no torch/CUDA import; no model load; no fake device.**
- **Rationale:** Frozen §14 requires the GPU-owner skeleton without an AI framework; Phase 5 has no model, so CPU-only must pass; the real RTX 3070 lets the GPU-present path be tested too.
- **Tradeoffs:** `nvidia-smi` parsing is vendor-specific (acceptable — it's optional; absence → CPU). VRAM budgeting is an interface until Phase 6.
- **Future consequence:** Phase 6 plugs real model VRAM estimates into `can_fit`/reservation with no interface change; multi-GPU is interface-ready.

---

### Final summary for reviewer
1. **Current baseline:** Python 3.12.9 (`backend/.venv`), av 13.1.0, **188 passed / 91% coverage** reproduced live; 10 apps; 12 migrations; greenfield for processing. Global Python 3.14 + torch cu128 is **machine-level only, not a project dep** (env-drift documented, not repaired).
2. **Frozen Phase 5 scope:** Processing Session Engine + CV Runtime skeleton + GPU Manager — lifecycle/heartbeats/recovery, **no detection** (detection = Phase 6). Frozen state machine includes PAUSE/RESUME/STOP.
3. **Recommended D1–D10:** B · A · dedup · PyAV · all-3-sampling · hybrid-progress · new-session-retry · one-session · lightweight-GPU-manager · **NumPy as Phase 5 runtime dep (canonical `rgb24` ndarray, lazy/sampled-only, `numpy==2.2.6`)**.
4. **Estimated effort:** ~12–15 developer-days (frozen: 7/12/20).
5. **Major risks:** interpreter drift, FFmpeg licensing, Windows lifecycle, single-writer discipline, synthetic-benchmark optimism, scope creep to detection.
6. **File created:** `E:\ai camera\PHASE_5_PLAN.md` (this document only).

PHASE 5 PLAN STATUS: READY FOR REVIEW

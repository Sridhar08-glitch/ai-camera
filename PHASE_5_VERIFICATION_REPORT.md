# PHASE 5 — VERIFICATION REPORT

**Phase:** Processing Session Engine + CV Runtime Skeleton + GPU Manager
**Date:** 2026-07-15
**Authoritative source:** `PHASE_0_ARCHITECTURE.md` (frozen) + approved `PHASE_5_PLAN.md` (D1–D10)
**Scope discipline:** strictly no-AI. No detection/tracking/counting. No external AI model/API. No RTSP/CCTV/webcam/live.

---

## 1. ACTUAL ENVIRONMENT / DEPENDENCY VERSIONS

| Item | Value |
|---|---|
| Interpreter | **Python 3.12.9** (`backend/.venv`; global 3.14 unused) |
| Django | 5.2.7 · DRF 3.16.1 · Channels 4.3.1 · Celery 5.5.3 · redis-py 6.4.0 |
| PyAV | **av==13.1.0** (bundled libav; libx264 available) |
| **NumPy (new, runtime)** | **numpy==2.2.6** (BSD-3-Clause) — `requirements/base.txt` |
| psutil (new, dev) | psutil==7.2.2 — `requirements/dev.txt` |
| PostgreSQL | 18 (native), app role `aitraffic_app` (non-superuser) |
| Redis | Memurai (native Windows), db0/1/2 |
| GPU | **NVIDIA RTX 3070 Laptop, 8192 MiB, driver 592.00, CUDA 12.8**, `nvidia-smi` present |
| Torch in project venv | **absent** (global torch is machine-level, never imported) |
| OS | Windows 11 |

**AI dependencies added:** none. No PyTorch/TensorFlow/Ultralytics/OpenCV/pretrained weights/CUDA toolkit. NumPy is a numeric-array primitive (the type PyAV's `to_ndarray()` produces), not an AI framework.

---

## 2. NUMPY DEPENDENCY GATE — PASSED

1. **Installed** `numpy==2.2.6` in `backend/.venv` (Python 3.12.9). Pinned in `requirements/base.txt`. (Fallback `1.26.4` documented; **not used** — no compatibility failure occurred.)
2. **NumPy imports:** ✅ `numpy 2.2.6`.
3. **PyAV still functional:** ✅ `av 13.1.0` opens/decodes; unaffected.
4. **`VideoFrame.to_ndarray(format="rgb24")`:** ✅ returns an array.
5. **Canonical contract verified:** shape `(H, W, 3)` ✅ · dtype `uint8` ✅ · C-contiguous ✅ · **RGB channel order** (solid-red round-trip → channel 0 == 255, ch1/2 == 0) ✅.

### 2.1 Benchmark results (§36 four-variant matrix)
Python 3.12.9 / numpy 2.2.6 / av 13.1.0 / psutil 7.2.2. Synthetic `testsrc` CFR clips (optimistic upper bound vs real H.264; decode is not the bottleneck).

| Clip | V1 decode-only | V2 decode+PyAV-RGB (no NumPy) | V3 decode+`to_ndarray(rgb24)` | V4 EVERY_N=5 + `to_ndarray` (accepted only) |
|---|---|---|---|---|
| 720p30 (450f) | 3371 fps / 47 MB | 660 fps / 62 MB | 767 fps / 71 MB | **1867 fps** (90 converted) / 71 MB |
| 1080p30 (600f) | 1721 fps / 78 MB | 300 fps / 99 MB | 436 fps / 93 MB | **1058 fps** (120 converted) / 93 MB |

**Findings:** (a) `to_ndarray(rgb24)` is *faster* than a manual reformat+copy (V3 > V2) and uses less memory; (b) sampling-before-conversion gives ~2.4× throughput (V4 vs V3) by converting only accepted frames; (c) **peak RSS is bounded** (~93 MB at 1080p) and independent of clip length — no full-video buffering. Memory measured with psutil (the earlier ctypes probe was replaced).

### 2.2 Real end-to-end run (live dev Postgres + Redis + GPU)
Seeded a VALID 320×240@15 fps×3 s video (45 frames) + session, then ran `manage.py run_cv_runtime --once`:
`QUEUED → INITIALIZING → RUNNING → COMPLETING → COMPLETED`; framecount processor (NumPy conversion every frame); **device `cuda:0`** (detected, tagged; CPU compute — no model); decode 352 fps / processed 352 fps; 45/45 frames; 100%; 0.45 s. Seeded data cleaned up afterward (dev DB restored).

---

## 3. IMPLEMENTED

### Backend — new app `apps.processing`
- **Models** (`models.py`, migration `0001`): `ProcessingConfigSnapshot` (immutable, content-hash-deduped, save-guard) and `ProcessingSession` (bounded progress, retry lineage, `CheckConstraint` on state, partial unique index `uq_processing_active_per_video`).
- **State machine** (`states.py`): 12 states, frozen transition table, terminal/non-terminal/runtime-active sets, per-state timestamp map. Single authoritative writer `services/state.py::transition()` (validates, stamps, audits, logs, metrics; `InvalidTransition`).
- **Snapshot capture** (`services/snapshot.py`): canonical payload from `versioned_payload()`, `canonical_hash`, dedup, camera-less support.
- **Session services**: `services/session.py` (create + retry, duplicate-active guard, param validation), `services/commands.py` (pause/resume/stop/cancel + pre-pickup cancel), `services/claim.py` (`FOR UPDATE SKIP LOCKED` atomic claim + concurrency cap), `services/params.py` (immutable execution params).
- **CV runtime** (`runtime/`): `video_source.py` (PyAV `LocalFileSource`, sequential decode, PTS, corrupt-frame skip+count, cleanup), `frames.py` (`FrameMeta` + lazy cached `FrameView.as_rgb_ndarray()`), `sampling.py` (EVERY_FRAME / EVERY_N / TARGET_FPS), `processors/` (Protocol + `NoOpFrameProcessor` + `FrameCountProcessor`), `gpu.py` (framework-independent `GPUManager`, nvidia-smi, reserve/release, `can_fit` stub), `heartbeat.py`, `pipeline.py` (linear orchestrator: decode→sample→process→bounded progress+heartbeat→command check→cleanup).
- **Watchdog** (`tasks.py`): Celery-beat `reconcile_stale_sessions` (60 s) — only processing work in Celery.
- **API** (`views.py`, `serializers.py`, `urls.py`, `permissions.py`): `/api/v1/processing-sessions` (+ `cancel`/`stop`/`pause`/`resume`/`retry`/`snapshot`) and non-gating `/api/v1/processing/runtime-status`. State never settable via API.
- **Management command** `run_cv_runtime` (graceful SIGINT/SIGBREAK/SIGTERM) + `scripts/dev_cv_runtime.ps1`.
- **Integrations**: retention hook `_video_is_protected` wired; audit `EventType` (11 processing events, `audit/0003`); observability allowlist (counters/summaries, no high-cardinality labels); structured logging; CV_* settings.

### Frontend — `apps/web` (Next.js)
`lib/processingApi.ts`; `/admin/processing` (list + runtime/GPU status, polling); `/admin/processing/[id]` (progress bar, frames, source timestamp, FPS, snapshot hash, pause/resume/stop/cancel/retry); **Start Processing** on the video detail page (role-gated, VALID-only); sidebar link. UI states clearly it performs no AI detection.

### ADRs
ADR-024 (session architecture/state machine), ADR-025 (CV runtime boundary), ADR-026 (immutable snapshot), ADR-027 (GPU resource management) — describe what shipped.

---

## 4. VERIFIED (mandatory acceptance criteria)

| Criterion | Result |
|---|---|
| Existing 188-test baseline green | ✅ 188 still pass |
| All new Phase 5 tests pass | ✅ 57 new (models 16, runtime 15, api 11, failure 15) |
| **Total suite** | ✅ **245 passed, 0 failed, 0 skipped** |
| ProcessingSession lifecycle end-to-end | ✅ unit + real dev-DB run (45 frames → COMPLETED) |
| Pause / resume / stop / cancel actually work | ✅ cancel/stop stop the loop; pause→resume returns to RUNNING; pre-pickup cancel |
| Immutable config snapshots | ✅ save-guard blocks mutation |
| Snapshot hashes deterministic | ✅ equals `canonical_hash(payload)`; dedup by hash |
| Config changes can't mutate historical snapshots | ✅ live ROI edit bumps revision; snapshot hash unchanged |
| Full sequential video processing | ✅ 6/45/60-frame clips fully decoded+processed |
| PTS-based frame timestamps | ✅ 100% PTS present; monotonic; `pts*time_base` authoritative |
| All approved sampling modes | ✅ EVERY_FRAME, EVERY_N (subset asserted), TARGET_FPS |
| Lazy NumPy conversion | ✅ `as_rgb_ndarray()` cached (one `to_ndarray` per frame) |
| Skipped frames not converted | ✅ NoOp never converts; EVERY_N converts == processed, not decoded |
| Memory bounded on longer clips | ✅ <150 MB growth over 60 frames (test); ~93 MB peak (benchmark) |
| Progress writes bounded | ✅ throttled (interval/every-N + forced final); no per-frame DB writes |
| Runtime heartbeat + stale recovery | ✅ watchdog FAILs stale (heartbeat_lost); ignores fresh |
| Duplicate execution prevented | ✅ atomic claim exclusive; partial unique index; duplicate-active 409 |
| Active session protects source video | ✅ `_video_is_protected` True while non-terminal; PROTECT FK |
| CPU-only operation | ✅ processors CPU-only; no CUDA dependency |
| GPU detection without PyTorch | ✅ nvidia-smi detects RTX 3070; no torch import; no fake device; CPU fallback |
| Runtime crash recovery | ✅ watchdog → FAILED conservatively (no auto-rerun) |
| Permissions enforced server-side | ✅ operator/admin control; analyst read-only; viewer 403 |
| Audit + observability integrations | ✅ lifecycle events audited; bounded metrics registered |
| Frontend processing workflow | ✅ typecheck clean; production build clean (routes compiled) |
| Clean migration from empty DB | ✅ `pytest --create-db` recreates + migrates all 15; passes |
| `makemigrations --check` | ✅ no changes detected |
| Ruff | ✅ clean (entire backend) |
| Windows runtime manually verified | ✅ `run_cv_runtime --once` real run + graceful exit |
| No AI / RTSP / detection introduced | ✅ explicit test asserts no detection-like output |

### Migration integrity
15 migrations (was 12): `+processing/0001_initial`, `+audit/0003` (EventType choices), `+retention/0003` (see Known Limitations #1). Phase 0→5 chain intact; applied by non-superuser `aitraffic_app`; no historical migration edited; no superuser DDL.

---

## 5. ACTUAL TEST RESULTS
```
245 passed, 0 failed, 0 skipped   (188 baseline + 57 new)
coverage (apps): 88% overall
  apps/processing/models.py 97% · states/frames/snapshot/infra ≥97% · pipeline 86%
  · views 90% · services 79–95% · gpu 54% (nvidia-smi branch), heartbeat 56%,
    run_cv_runtime.py 0% (long-lived process loop — exercised via live E2E, not unit)
Ruff: All checks passed
Frontend: tsc --noEmit clean · next build succeeded (all routes incl. /admin/processing)
```

---

## 6. KNOWN LIMITATIONS

1. **Pre-existing Phase-4 migration drift (resolved additively).** `DataCategory` gained `VIDEO_THUMBNAIL`/`TRAFFIC_CONFIG` in Phase 4 but `RetentionPolicy.category`'s choices migration was never regenerated (choices-only, no DB effect — tests still passed). Discovered during Phase 5; resolved with additive `retention/0003_alter_retentionpolicy_category` (no data change, no historical edit). Documented rather than silently absorbed.
2. **Interpreter drift (environment).** The machine's global Python 3.14 + torch cu128 shadows the project venv in a naive shell (and lacks `structlog`, so it can't even collect tests). All scripts pin `backend/.venv`. Recommend a startup interpreter-version guard (not implemented in Phase 5).
3. **`run_cv_runtime` command has 0% unit coverage** — it is a long-lived process loop; its logic (`claim_next` + `run_session`) is fully unit-tested and the command was verified via a live end-to-end run. A harness-level test of the loop is deferred.
4. **Benchmark clips are synthetic (`testsrc`, CFR).** Real H.264 traffic footage will be slower and may exercise VFR paths; the VFR code path uses real PTS but was exercised only with crafted timestamps in unit tests, not a true VFR fixture.
5. **GPU manager `nvidia-smi` branch partially covered** (54%) — the CUDA-present parse and CPU-fallback are tested; multi-GPU enumeration and VRAM-exhaustion are interface-only (Phase 6).
6. **FFmpeg licensing (inherited, ADR-023)** — PyAV bundles libav; review required before commercial redistribution. Not a Phase 5 blocker.
7. **Real-time progress** ships as REST polling; the WebSocket overlay (frozen §18) is designed (Redis pub/sub is published on commands) but the Channels relay consumer is deferred — polling is fully sufficient and DB is authoritative.

---

## 7. DEFERRED TO PHASE 6+
Detection provider (YOLO/RT-DETR/etc.), tracking, lane association, counting, speed, congestion, queue, incidents, alerts, analytics, prediction, SUMO, signals, twin. Real GPU model loading + VRAM budgeting with real estimates. Multi-GPU scheduling. RTSP/CCTV/webcam/live. Resume-from-checkpoint (idempotent measurements). WebSocket progress relay consumer. Real-VFR/real-footage benchmark fixtures. `numpy` remains the array contract Phase 6 detectors consume via `FrameView.as_rgb_ndarray()` — no pipeline redesign required.

---

## 8. VERIFICATION PROCEDURE (reproduce)
```
# backend (project venv)
cd backend
.\.venv\Scripts\python.exe -m pytest -q                 # 245 passed
.\.venv\Scripts\python.exe -m pytest --create-db -q     # clean migration from empty DB
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run   # no changes
.\.venv\Scripts\ruff.exe check .                        # clean
.\.venv\Scripts\python.exe manage.py run_cv_runtime --once              # runtime up, GPU detected
# frontend
cd ../frontend
npx tsc --noEmit                                        # clean
npx next build                                          # clean
```

---

## 9. SUMMARY

Phase 5 delivers the complete no-AI execution foundation: a durable, single-writer `ProcessingSession` state machine (START/PAUSE/RESUME/STOP/CANCEL + heartbeats), an immutable content-addressed configuration snapshot, a standalone CV runtime that decodes real video frame-by-frame with PyAV, three deterministic sampling modes, a lazy NumPy `rgb24` frame contract (converted only for sampled frames, cached, bounded memory), a framework-independent GPU manager (RTX 3070 detected without PyTorch, CPU-first), conservative stale-session recovery, retention protection, and server-side-enforced APIs + frontend — all with **zero vehicle detection**. 245 tests pass, migrations are clean from an empty database, and the runtime was verified end-to-end on Windows. Every mandatory acceptance criterion passed.

PHASE 5 STATUS: COMPLETE

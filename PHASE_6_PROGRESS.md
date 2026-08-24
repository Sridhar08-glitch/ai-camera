# PHASE 6 — IMPLEMENTATION PROGRESS / RESUME HANDOFF

**Status:** ✅ COMPLETE — 2026-07-16. See `PHASE_6_VERIFICATION_REPORT.md` (`PHASE 6 STATUS: COMPLETE`).
All NEXT items 0–7 done. 297 tests pass (baseline 245 + 52 new); `manage.py check` clean; migrations clean; torch absent. `onnx==1.17.0` added (schema helper for the TEST artifact; not torch/training/weights). Below is the historical handoff (kept for provenance).

**Status (historical):** IN PROGRESS — paused 2026-07-15. Safe state (`manage.py check` clean; migrations applied).
**Scope:** Phase 6 = detection **infrastructure only** (approved plan `PHASE_6_PLAN.md`, D1–D15). No third-party pretrained weights, no training, no datasets. Real detector = Phase 6T (deferred). ONNX Runtime = production inference boundary; PyTorch NOT installed.

---

## ENVIRONMENT
- Project venv `backend/.venv` (Python 3.12.9). Never use global 3.14 / global torch.
- Baseline **245 tests passed** (verified at start of Phase 6, before edits).
- **onnxruntime==1.20.1 INSTALLED + pinned in `requirements/base.txt`.** Providers available: `CPUExecutionProvider` (+Azure) — **no CUDA EP** (CPU package; `onnxruntime-gpu`+cuDNN would be needed for GPU, NOT installed per §19). No torch pulled in.
- GPU hardware: RTX 3070 Laptop / 8 GB / nvidia-smi present (Phase 5 GPUManager detects it), but ONNX CUDA EP not available with CPU package.

## KEY REPO FACTS (verified this session)
- `settings.ARTIFACT_ROOT` = `BASE_DIR/artifacts` (governance model artifacts live here; `validate_artifact_path()` in `apps/governance/checksums.py` guards it). Video storage is separate (`VIDEO_STORAGE_ROOT`).
- Processor registry: `apps/processing/runtime/processors/infra.py::_REGISTRY` + `build_processor()`. Params validated in `apps/processing/services/params.py` (`allowed_top={"sampling","processor","device_preference"}`; a processor auto-allowed once in `_REGISTRY`).
- FrameProcessor Protocol: `apps/processing/runtime/processors/base.py` (`setup(ctx)/process(view,ctx)/teardown()`, `ProcessingContext{snapshot_payload,params,device,logger}`, `ProcessorResult`, `ProcessorSummary`).
- `FrameView.as_rgb_ndarray()` lazy-cached rgb24 (H×W×3 uint8 C-contig) — `apps/processing/runtime/frames.py`.
- GPUManager: `apps/processing/runtime/gpu.py` (`select_device/reserve/refresh/release/can_fit/status`).
- Governance activate: one active version per family, `IsSystemAdmin`. Router auto-routes @action methods (no urls edit needed for new actions).

---

## DONE (committed to working tree)
1. **ONNX dependency gate** — installed/pinned onnxruntime 1.20.1; verified EPs; no torch.
2. **`apps/processing/taxonomy.py`** — canonical taxonomy v1 `{0 CAR,1 BUS,2 TRUCK,3 MOTORCYCLE,4 BICYCLE,5 PEDESTRIAN}`, `TAXONOMY_VERSION="v1"`, helpers.
3. **`apps/processing/runtime/detector/contract.py`** — framework-independent `Detection` (canonical **normalized XYXY** in [0,1], `validate()` rejects NaN/Inf/out-of-range/x2<x1, `to_dict()`), `DetectionResult` (provider identity + `is_test_provider`), `DetectionError(code)`.
4. **`apps/processing/models.py`** — added `FrameDetectionBatch` (session PROTECT, video PROTECT, model_version PROTECT nullable, provider_name/version, `is_test_provider`, taxonomy_version, source_frame_index, pts_seconds, detection_count, `detections` JSONField, unique (session,frame), indexes). Imports `AIModelVersion`.
5. **`apps/governance/models.py`** — added `ModelLifecycle` enum `{draft,training,evaluated,candidate,approved,active,retired,test_only}` + `AIModelVersion.status` field (default draft).
6. **`apps/governance/views.py`** — added `approve` action + hardened `activate`: TEST_ONLY can NEVER be approved/activated; only APPROVED→ACTIVE; sets status=ACTIVE + is_active; demotes prior active to APPROVED; audits `MODEL_APPROVED`/`MODEL_ACTIVATED`. Added `status` import + `ModelLifecycle`.
7. **`apps/audit/models.py`** — added `EventType.MODEL_APPROVED`.
8. **`apps/processing/retention_handlers.py`** — `DetectionMetadataRetentionHandler` (DETECTION_METADATA, bounded purge of FrameDetectionBatch). **NOT yet wired into `apps.py ready()`** (see NEXT #0).
9. **Migrations applied + clean:** `governance/0003_aimodelversion_status`, `processing/0002_framedetectionbatch`, `audit/0004_alter_auditevent_event_type`. `makemigrations --check` = clean. Total now 18 migrations.

**Not yet run since edits:** full test suite (was 245 green pre-edits; new models untested). `manage.py check` passes.

---

## NEXT (resume here, in order)
0. **Wire retention handler:** add `from apps.processing import retention_handlers  # noqa` to `apps/processing/apps.py::ready()` (currently only imports `observability`). Then run suite to confirm no import cycle (processing.retention_handlers imports models lazily — OK).
1. **Detector runtime** (`apps/processing/runtime/detector/`):
   - `base.py` — `DetectorProvider` Protocol: `load(ctx)/warmup()/preprocess(rgb)/infer()/postprocess()->DetectionResult/classes()/unload()`; device policy input.
   - `device.py` — policy `REQUIRE_GPU|PREFER_GPU|CPU_ONLY`; resolve ONNX EP list from GPUManager device + `ort.get_available_providers()`; **truthful** actual-EP reporting; no silent GPU pretend. Setting `CV_DETECTOR_DEVICE_POLICY` (default PREFER_GPU).
   - `preprocess.py` — aspect-ratio-preserving **letterbox** to target (default 640) from rgb24 ndarray; return tensor(NCHW float) + `LetterboxMeta(scale, pad_x, pad_y, orig_w, orig_h)`. Pure NumPy (no torch).
   - `postprocess.py` — output validation (NaN/Inf/shape), confidence filter, **class map** (model idx→canonical), **reverse letterbox** → normalized XYXY, clamp [0,1], **NMS** (pure NumPy). Deterministic-fixture tested; thresholds marked PROVISIONAL.
   - `onnx_backend.py` — `OnnxDetector`: create `ort.InferenceSession(path, providers=...)` per device policy, validate input/output specs, run, cleanup; loads only validated ONNX (no pickle).
   - `test_provider.py` — `DeterministicTestProvider` (name="test", `is_test_provider=True`): emits fixed reproducible boxes from frame meta (e.g. seeded by frame index). **Never real AI.** Cannot be registered as production.
   - `artifact.py` — validate before load: exists, size, sha256 vs `ModelArtifact.checksum_sha256`, format=onnx, model-version status (reject TEST_ONLY-as-production / unapproved), resolve under ARTIFACT_ROOT via `validate_artifact_path`.
   - Optional: helper to build a **safe minimal project-created ONNX test artifact** (identity/const graph, classified TEST_ONLY) for onnx_backend tests — no third-party weights.
2. **DetectionFrameProcessor** (`runtime/processors/detection.py`): implements FrameProcessor; `setup()` resolves provider (active APPROVED AIModelVersion for task=detection, OR the deterministic test provider when params select `"test"`), **loads model once**, reserves device; `process()` → `view.as_rgb_ndarray()` → provider → `DetectionResult` → buffer; **batched persist** FrameDetectionBatch (bulk_create per N frames + final flush); `teardown()` flushes + unloads. Register `"detector"` in `_REGISTRY`; extend params `allowed_top` with a `detector` block (`{model_version_id?|"test", conf?, iou?}`). Preserve NoOp path. Sampling-before-conversion already holds (pipeline calls processor only for sampled frames).
3. **APIs/permissions/audit/observability/benchmark** (task #15): detections API `GET /api/v1/processing-sessions/{id}/detections?frame=&from_ts=&to_ts=` (paginated) + `/detections/{frame_index}`; permission matrix (viewer excluded; analyst read; operator/admin start; sysadmin governance); observability metrics (detector_preprocess/inference/postprocess/persist ms, detection_frames_total, failures) added to `apps/processing/observability.py` allowlist; benchmark harness (infra, deterministic provider) + PROVISIONAL Q/B/P profile config.
4. **Frontend** (task #16): `/admin/processing/[id]` detections view — boxes+class+confidence+provider; **`TEST PROVIDER — NOT REAL AI DETECTION`** banner when `is_test_provider`. No counts/tracking/speed. processingApi extension.
5. **Tests** (§31 full list) + failure tests (§27) + full regression (must stay ≥245) + real-video infra verify (deterministic provider) + clean setup.
6. **ADR-028** (Detector arch + AI framework boundary: ONNX runtime, no third-party weights), **ADR-031** (FrameDetectionBatch storage), **ADR-032** (ONNX artifact + loading lifecycle). ADR-029/030 = Phase 6T direction (mark "accepted direction, not yet implemented").
7. **`PHASE_6_VERIFICATION_REPORT.md`** per §38; end `PHASE 6 STATUS: COMPLETE` only if all §37 criteria pass, else `PHASE 6 STATUS: BLOCKED`.

## GUARDRAILS (do not violate)
No third-party pretrained weights anywhere (not even benchmark). No PyTorch/dataset/training in Phase 6. Deterministic provider always labelled TEST, never activatable. No real mAP/precision/recall/accuracy claims. No tracking/counting/speed/congestion. CV runtime owns model load (Django/Celery never load). Model loaded once, reused, released. Empty detections ≠ inference failure. Keep 245 baseline green; don't weaken tests.

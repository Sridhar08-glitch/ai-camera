# PHASE 6 — VERIFICATION REPORT

**Phase:** Object Detection **Infrastructure** (runtime + ONNX boundary + storage + API + governance gate)
**Date:** 2026-07-16
**Authoritative source:** `PHASE_0_ARCHITECTURE.md` (frozen) + approved `PHASE_6_PLAN.md` (D1–D15) + `PHASE_6_PROGRESS.md`
**Scope discipline:** detection **infrastructure only** — **no third-party pretrained weights, no training, no datasets, no Phase 6T**. Deterministic TEST output is explicitly **not real AI** and makes **no accuracy claim**.

---

## 1. ACTUAL ENVIRONMENT / DEPENDENCY VERSIONS

| Item | Value |
|---|---|
| Interpreter | **Python 3.12.9** (`backend/.venv`; global 3.14 / global torch unused) |
| Inference runtime | **onnxruntime==1.20.1** (MIT). EPs available: `CPUExecutionProvider` (+Azure). **No CUDA EP** (CPU build). |
| ONNX authoring | **onnx==1.17.0** (Apache-2.0) — builds/validates ONNX containers (TEST artifact). Not torch, not training, not weights. |
| NumPy | numpy==2.2.6 (pure-NumPy preprocess/postprocess/NMS) |
| PyTorch in project venv | **absent** (`import torch` → ModuleNotFoundError; verified post-work) |
| GPU hardware | NVIDIA RTX 3070 Laptop (8 GB), `nvidia-smi` present — but ONNX CUDA EP not available with the CPU package |
| OS | Windows 11 |

**AI dependencies added this phase:** `onnx==1.17.0` only (schema/graph helper for authoring the project-created TEST artifact). **No** PyTorch / TensorFlow / Ultralytics / OpenCV / pretrained weights / CUDA toolkit / datasets.

---

## 2. WHAT SHIPPED (traceable to plan D1–D15 / NEXT 0–7)

### 2.1 Detector runtime — `apps/processing/runtime/detector/`
- **`contract.py`** — `Detection` (canonical **normalized XYXY [0,1]**, `validate()` rejects NaN/Inf/oob/`x2<x1`), `DetectionResult` (+`is_test_provider`), `DetectionError(code)`. *(pre-existing, preserved)*
- **`base.py`** — `DetectorProvider` Protocol (`load/warmup/classes/detect/unload`).
- **`device.py`** — `DevicePolicy {REQUIRE_GPU,PREFER_GPU,CPU_ONLY}`; resolves ONNX EP list from policy + GPUManager tag + `ort.get_available_providers()`; **truthful** `actual_ep` recorded from the live session; REQUIRE_GPU fails loudly, PREFER_GPU falls back to CPU honestly.
- **`preprocess.py`** — aspect-preserving **letterbox** → NCHW float tensor + `LetterboxMeta`. Pure NumPy.
- **`postprocess.py`** — validation → conf filter → class map → **reverse letterbox** → clamp → **per-class NMS** → bounded cap. Pure NumPy.
- **`onnx_backend.py`** — `OnnxDetector`: real `ort.InferenceSession(providers=…)`, input/output spec validation, per-stage timings, decode of `phase6-infra-v1` `(N,6)` output. Loads only validated ONNX.
- **`test_provider.py`** — `DeterministicTestProvider` (`name="test"`, `is_test_provider=True`) — reproducible pseudo-boxes from frame content. **Never real AI, never activatable.**
- **`artifact.py`** — pre-load validation: governed `ModelArtifact`, confined under `ARTIFACT_ROOT`, present/non-empty/size-consistent, **sha256-consistent**, ONNX-sniffed (rejects pickle), lifecycle gate (rejects TEST_ONLY/unapproved).
- **`testkit.py`** — builds a minimal real ONNX TEST artifact (const `(N,6)` graph) so the ONNX boundary is verified with a genuine session.
- **`factory.py`** — provider resolution honoring the production gate (`test` → TEST provider; UUID → governed version; omitted → ACTIVE detection version).
- **`profiles.py`** — PROVISIONAL Q/B/P runtime profiles (speed knobs only, no accuracy claim).
- **`benchmark.py`** — **speed-only** harness (throughput + per-stage latency); no mAP/precision/recall.

### 2.2 Pipeline integration
- **`processors/detection.py`** — `DetectionFrameProcessor` implements the Phase 5 FrameProcessor Protocol; loads the provider **once** in `setup()`, `detect()` per sampled frame, **bulk_create** every `CV_DETECTOR_PERSIST_EVERY_N` frames (+ final flush, `ignore_conflicts`), unloads on teardown. Per-frame inference errors are skipped (empty ≠ failure); load errors are fatal.
- Registered `"detector"` in the processor registry (lazy import); `ProcessingContext` gained `session_id`/`video_id`; params `allowed_top` gained a validated `detector` block.

### 2.3 Storage / retention (ADR-031)
- `FrameDetectionBatch` (pre-existing model, preserved) + `DetectionMetadataRetentionHandler` **now wired** into `apps/processing/apps.py::ready()` (NEXT #0). Registration verified.

### 2.4 API / permissions / observability / governance
- `GET /processing-sessions/{id}/detections` (paginated; `frame`,`from_ts`,`to_ts` filters) + `/detections/{frame_index}`. Read gated to processing readers (**viewer + incident_operator excluded**; analyst read; operator/admin control).
- Observability: `detector_preprocess/inference/postprocess_ms`, `detector_persist_ms`, `detection_frames_total`, `detector_failures_total` added to the allowlist.
- Governance production gate: `approve` action + hardened `activate` (only APPROVED→ACTIVE; TEST_ONLY never; demotes prior active; audits `MODEL_APPROVED`/`MODEL_ACTIVATED`). *(pre-existing edits, preserved + regression-tested)*

### 2.5 Frontend
- `/admin/processing/[id]` → `DetectionsPanel`: per-frame boxes (normalized coords, **no raw frame shown** — privacy §32), class + confidence + provider identity, frame navigation, and a prominent **“TEST PROVIDER — NOT REAL AI DETECTION”** banner when `is_test_provider`. No counts/tracking/speed. `processingApi.ts` extended; `tsc --noEmit` clean.

---

## 3. VERIFICATION EVIDENCE

### 3.1 ONNX Runtime boundary (real session)
Built a real TEST ONNX, loaded it in `OnnxDetector`, ran a 480×640 frame:
- `actual_ep = CPUExecutionProvider`, `using_gpu = False` — **truthful** (no fake GPU).
- Reverse-letterbox math exact: target-px `[100,100,260,300]` on a 480×640 frame (scale 1.0, pad_y 80) → normalized `[0.15625, 0.041667, 0.40625, 0.458333]`. ✅
- Deterministic TEST provider reproducible across calls; `is_test_provider=True`. ✅

### 3.2 Real-video pipeline verification (deterministic provider + governed ONNX)
`tests/test_detection_pipeline.py` runs the **actual pipeline** on real decodable video:
- TEST provider: 6-frame clip → 6 `FrameDetectionBatch` rows, `is_test_provider=True`, `taxonomy_version=v1`, `model_version=None`, valid normalized bboxes. ✅
- Governed ONNX (APPROVED+active): 5-frame clip → 5 rows, `is_test_provider=False`, `provider_name` = family, `model_version_id` set, 2 boxes/frame. ✅
- Batched persistence: 10 frames with `PERSIST_EVERY_N=3` → all 10 rows, indices 0–9 complete/unique. ✅
- **Empty ≠ failure**: conf=0.99 → every frame `detection_count=0`, session **COMPLETED**, `error_code=""`. ✅

### 3.3 Production-gate & safety failure tests (`tests/test_detector_failure.py`)
TEST_ONLY rejected (`model_not_approved`) · DRAFT rejected · checksum mismatch (`checksum_mismatch`) · size mismatch (`invalid_artifact`) · missing file (`artifact_missing`) · **pickle-as-ONNX rejected** (`invalid_artifact`, never unpickled) · omitted selector with no ACTIVE model → `no_active_model` (no silent bind) · unknown id → `model_not_found` · **REQUIRE_GPU on CPU build → hard `DeviceResolutionError`** (no fake GPU). ✅

### 3.4 Governance regression
The pre-existing `test_activation_single_active_and_audited` was adapted to the new **production gate** (DRAFT activate now → 409; approve→activate→demote-to-APPROVED path asserted, `MODEL_APPROVED`+`MODEL_ACTIVATED` audited). Strengthened, not weakened. ✅

### 3.5 Full regression
```
python -m pytest   →  297 passed, 0 failed   (baseline 245 + 52 new Phase 6 tests)
manage.py check    →  0 issues
makemigrations --check --dry-run  →  No changes detected
import torch       →  ModuleNotFoundError (runtime torch-free)
```

### 3.6 Benchmark (speed only — no accuracy)
`benchmark_detector` sample (CPU, 640² balanced): TEST provider ≈ 400 fps; ONNX TEST artifact ≈ 138 fps with stage means `preprocess≈4.6ms / inference≈0.17ms / postprocess≈0.27ms`. Report carries `"accuracy_note": "SPEED ONLY — no accuracy/mAP/precision/recall measured or implied."` ✅

---

## 4. ACCEPTANCE CRITERIA (§37) — MAPPING

| Criterion | Status | Evidence |
|---|---|---|
| Full regression green (≥245) | ✅ | 297 passed |
| Detection **infrastructure** + benchmark harness; **no training/production model** | ✅ | §2, §3.6 |
| AI-framework + architecture + pretrained-policy documented (ADRs) | ✅ | ADR-028/031/032 (+029/030 direction) |
| **NO third-party pretrained weights anywhere (incl. benchmark)** | ✅ | only `onnx`/`onnxruntime`; TEST artifact is a const graph |
| TEST detector labelled deterministic, no accuracy claim, cannot be `active` | ✅ | `is_test_provider`, banner, TEST_ONLY gate (§3.3) |
| Canonical taxonomy versioned; annotation format defined | ✅ | `taxonomy.py` v1; `Detection.to_dict` normalized_xyxy |
| `DetectorProvider` returns framework-independent detections | ✅ | `contract.py`, no ORT/torch types cross boundary |
| Detections retain frame/timestamp/session/model traceability | ✅ | `FrameDetectionBatch` fields (§2.3, §3.2) |
| Artifacts checksum-validated | ✅ | `artifact.py` (§3.3) |
| Only `approved`→`active` selectable for production | ✅ | governance gate + `resolve_onnx_artifact` (§3.3, §3.4) |
| Django/general-Celery never load weights; CV runtime owns loading | ✅ | load only in `DetectionFrameProcessor.setup` (CV runtime) |
| Model loaded **once** (not per frame) | ✅ | provider loaded in setup, reused, unloaded in teardown |
| Empty vs failure distinguishable | ✅ | §3.2 empty-not-failure test |
| Benchmark baselines + profile-selection (real per-model profiles → 6T) | ✅ | `benchmark.py` + `profiles.py` (PROVISIONAL) |

**Deviations / honest notes:**
1. **Added dependency `onnx==1.17.0`** (not in the original DONE list) — pinned in `requirements/base.txt`. Justification: it authors/validates the project-created TEST ONNX so the ONNX Runtime boundary is verified with a **real** `InferenceSession` instead of a mock. It is a schema/graph helper — **not** torch, training, a dataset, or weights — so it stays within Phase 6 guardrails. Torch remains absent.
2. Audit EventTypes `MODEL_VERSION_REGISTERED / MODEL_EVALUATION_RECORDED / MODEL_RETIRED` from the §38 design were **not** added: no register/retire endpoints exist in Phase 6 scope, so nothing would emit them. The promotion actions that *do* exist (approve, activate) are audited. No accuracy/eval action shipped, consistent with scope.
3. Raw single-tensor YOLO-head decoding is intentionally deferred to Phase 6T; Phase 6 uses the decoded `phase6-infra-v1` `(N,6)` output contract (ADR-032). Coordinate/NMS/postprocess contract is stable across that future change.

---

## 5. GUARDRAILS — CONFIRMED HELD
No third-party pretrained weights anywhere. No PyTorch/dataset/training. Deterministic provider always TEST, never activatable. No mAP/precision/recall/accuracy claims. No tracking/counting/speed/congestion. CV runtime owns model load; Django/Celery never load. Model loaded once, reused, released. Empty ≠ failure. 245 baseline preserved (now 297). Phase 6T **not** started.

---

## PHASE 6 STATUS: COMPLETE

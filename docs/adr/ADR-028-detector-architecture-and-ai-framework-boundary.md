# ADR-028 — Detector Architecture & AI Framework Boundary

**Status:** Accepted (Phase 6)

## Context
Phase 6 delivers detection **infrastructure only** (approved plan `PHASE_6_PLAN.md`,
D1–D15): the full runtime path that will host a real object detector, but with **no
third-party pretrained weights, no training, no datasets**. A real project-trained
detector arrives in Phase 6T. We need a framework boundary that (a) never leaks ML
tensors/classes into application code, (b) survives a model swap without changing
analytics semantics, and (c) can be verified end-to-end today without any weights.

## Decision
A layered, framework-independent detector runtime under
`apps.processing.runtime.detector`:

- **Contract (`contract.py`)** — `Detection` is the ONLY cross-boundary type. Canonical
  box representation is **normalized XYXY in [0,1]** (letterbox-inverted, resolution
  independent). `validate()` rejects NaN/Inf/out-of-range/`x2<x1`. No ONNX/torch types
  ever cross this boundary.
- **Taxonomy (`taxonomy.py`)** — canonical `{CAR,BUS,TRUCK,MOTORCYCLE,BICYCLE,
  PEDESTRIAN}`, versioned `v1`. Model-native class indices are mapped to canonical ids
  in postprocess, so swapping models never changes downstream semantics. PEDESTRIAN is
  bounding-box only (no recognition/identification).
- **`DetectorProvider` Protocol (`base.py`)** — `load / warmup / classes / detect /
  unload`. Two implementations satisfy it: the ONNX backend and the deterministic TEST
  provider. Loaded once per session, reused, released on teardown.
- **Preprocess (`preprocess.py`)** — aspect-ratio-preserving **letterbox** to a square
  target, pure NumPy, returning an NCHW float tensor + `LetterboxMeta`.
- **Postprocess (`postprocess.py`)** — validation → confidence filter → class map →
  **reverse letterbox** → normalize/clamp → **per-class NMS** (pure NumPy) → bounded cap.
- **ONNX backend (`onnx_backend.py`)** — the production inference boundary (see ADR-032).
- **TEST provider (`test_provider.py`)** — deterministic pseudo-boxes from frame content;
  `is_test_provider=True`; **never real AI**, never activatable as production.

**AI framework boundary:** the runtime's production inference dependency is **ONNX
Runtime** (`onnxruntime`, CPU EP always; CUDA EP only with `onnxruntime-gpu`+cuDNN, not
installed here). The `onnx` authoring library is used only to build/validate ONNX
containers (e.g. the project-created TEST artifact). **PyTorch is NOT a runtime
dependency** and is not installed — it is a Phase 6T *training-only* concern. Django and
Celery never load a model; only the CV runtime does (frozen §14).

## Consequences
- Phase 6T supplies a governed, project-trained ONNX detector + a versioned class map;
  no application code above the contract changes.
- Real YOLO-style raw-tensor head decoding is deferred to Phase 6T; the infra output
  contract is the decoded `phase6-infra-v1` `(N,6)` form (ADR-032), which keeps the
  coordinate/NMS/postprocess contract stable across that change.
- No accuracy (mAP/precision/recall) is claimed anywhere in Phase 6; deterministic TEST
  output is explicitly meaningless as detection.

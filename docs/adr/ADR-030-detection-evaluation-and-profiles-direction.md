# ADR-030 — Model Training & Weight Provenance (Phase 6T)

**Status:** Accepted — **Phase 6T-A implemented** (scratch-training infrastructure shipped; real model + evaluated profiles = 6T-B)

## Decision (6T-A implemented)
- **Random initialization, no third-party pretrained weights** (`training.architectures`):
  the first project detector starts from random init. No COCO/ImageNet/YOLOX/YOLO/RT-DETR
  pretrained weights. Any future exception requires explicit approval + provenance.
- **Architecture (D3/D4):** YOLOX-S (Apache-2.0) is the intended primary via a **training-only
  pinned dependency** (not vendoring); **torchvision FCOS (BSD-3, random init)** is the
  integrated first-class fallback in this environment; a `TinyDetector` provides fast,
  self-contained smoke verification. Production ships **only ONNX** — the runtime never
  imports the training framework.
- **Export + parity:** ONNX export with a fixed documented I/O contract + `onnx.checker`;
  **PyTorch↔ONNX parity** is required before promotion (a failed parity check is not a
  successful export). A raw architecture-native output is decoded by a registered adapter
  (`tiny_v1`, later `yolox_v1`) → the canonical Phase 6 `Detection` contract (never forced
  to the Phase 6 `(N,6)` **test** contract in-graph).
- **Quality gate:** baseline-measured; the first model may ship `EXPERIMENTAL`; a poor model
  is never activated to close a phase. Evaluation uses pycocotools mAP + slices (6T-B).

## Runtime profiles / evaluation direction (unchanged, 6T-B)
Operating points and accuracy evaluation need a real governed model + dataset (6T-B). This
section records the intended direction and the status of the provisional Phase 6 artifacts.

## Direction (not implemented in Phase 6)
- **Runtime profiles** (`detector/profiles.py`, Quality / Balanced / Performance) exist in
  Phase 6 as **PROVISIONAL infrastructure defaults only** — they bundle *speed/runtime*
  knobs and carry **no precision/recall/mAP guarantee**. Phase 6T will tune real operating
  points against evaluation.
- **Benchmark harness** (`detector/benchmark.py`, `benchmark_detector` command) measures
  **speed only** (throughput + per-stage latency) over synthetic frames with the TEST
  provider / TEST ONNX artifact. It never measures or implies accuracy. Phase 6T adds a
  real accuracy evaluation harness with governed datasets recorded on `ModelEvaluation`.
- Accuracy claims, dataset provenance, and profile-to-accuracy mappings are Phase 6T
  deliverables.

## Consequences
The profile and benchmark interfaces are stable; Phase 6T fills them with evaluated
numbers without changing the runtime or API surface. Any accuracy statement before that
work would be unfounded and is explicitly disallowed in Phase 6.

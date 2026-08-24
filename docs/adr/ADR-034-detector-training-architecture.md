# ADR-034 — Detector Training Architecture

**Status:** Accepted (Phase 6T-A)

## Context
Phase 6T needs a scratch-trainable, commercially-licensed detector that exports to ONNX and
runs on the existing Phase 6 runtime, trainable on an 8 GB RTX 3070, and effective for
small/distant traffic objects. The plan re-scored candidates (weighted) and selected a
primary + fallback.

## Decision
- **Primary: YOLOX-S (Apache-2.0)** — anchor-free, scratch-friendly, good small-object via
  FPN, clean ONNX export. Integrated as a **training-only pinned dependency** (ADR-033), not
  vendored: production ships only ONNX, so the training framework never enters the runtime.
- **Fallback: torchvision FCOS ResNet50-FPN (BSD-3)** — in-stack, zero external repo, random
  init (`weights=None, weights_backbone=None`), simplest decode. This is the architecture
  actually integrable in the offline 6T-A environment and is validated here.
- **`TinyDetector`** (project code) — a minimal random-init head used for fast, deterministic
  smoke verification of the train→checkpoint→resume→eval→export→parity plumbing. Not a real
  detector.
- **Output adapter boundary:** each architecture emits a raw native tensor decoded by a
  registered adapter id (`tiny_v1`; later `yolox_v1`) into (boxes_xyxy_target, scores,
  class_ids), which the existing Phase 6 postprocess turns into canonical `Detection`s. The
  adapter is pure NumPy so the identical decode runs on the PyTorch and ONNX outputs during
  parity.
- **Rejected:** Ultralytics YOLOv5/v8/11 (AGPL-3.0) and YOLOv7 (GPL-3.0) — copyleft
  incompatible with a closed commercial product.

## 6T-A environment note
YOLOX could not be pip-installed here (package index unreachable), so 6T-A integrates FCOS +
TinyDetector; `build_detector("yolox_s")` raises a clear, guided error. Full YOLOX-S training
is a 6T-B activity on a package-index-reachable / GPU host.

## Consequences
Swapping FCOS→YOLOX later is a training-side change with a new adapter id; the runtime
`Detection` contract is unchanged.

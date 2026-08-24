# ADR-033 — Training Environment Isolation

**Status:** Accepted (Phase 6T-A)

## Context
Phase 6T introduces PyTorch training, but the production runtime must stay lean and
ONNX-Runtime-only (ADR-028). Mixing torch into the backend would bloat the runtime, add
GPU/driver coupling, and violate the "CV runtime owns inference via ONNX" boundary.

## Decision
- A separate top-level **`training/`** package with its **own `training/.venv`** (Python
  3.12). Training-only dependencies (torch, torchvision, pycocotools, …) install there and
  **never** into `backend/requirements/*`.
- **`training/` never imports the Django backend** (verified by a source grep in CI). Shared
  contracts (canonical taxonomy size, the bilinear letterbox — ADR-037) are re-declared in
  `training/` and kept in sync via a shared golden hash, not by importing backend.
- The production backend keeps `import torch` failing; a regression check asserts this.
- **Environment reality (6T-A):** the CUDA wheel index (`download.pytorch.org`) was
  unreachable in the build environment, so the **CPU** torch stack (torch 2.13.0+cpu,
  torchvision 0.28.0+cpu) was installed and verified for smoke/infrastructure. GPU training
  uses the same device-agnostic code with a `cu126` wheel on a CUDA-index-reachable host
  (or rented GPU) — a documented, approved fallback.

## Consequences
Production deploys ONNX artifacts only. Training scale/GPU concerns are isolated to
`training/`. The two-environment split is the enforced boundary; `onnxruntime-gpu` (a
separate, later, prod-only decision — ADR-032/plan D17) does not change it.

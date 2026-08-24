# ADR-027 — GPU Resource Management

**Status:** Accepted (Phase 5)

## Context
Frozen §14 requires a GPU-owner skeleton: one process owns models/GPU; Django and
Celery never touch CUDA; single-model/single-session default on 8 GB VRAM; CPU
fallback tagged; a `device_id` interface for future multi-GPU. Phase 5 loads NO model
and must run CPU-only, so the manager cannot depend on an AI framework.

## Decision
`apps.processing.runtime.gpu.GPUManager` — **framework-independent**:
- **Detection** via `nvidia-smi --query-gpu=index,name,memory.total,memory.used,
  memory.free,driver_version --format=csv,noheader,nounits` (subprocess, short
  timeout). No `nvidia-smi` → **CPU mode** (not an error). Never imports torch/CUDA;
  never fabricates a device.
- **Device selection** honors `processing_params.device_preference`
  (`auto|cpu|cuda[:n]`); `auto` → first CUDA device if present else `cpu`. Phase 5
  processors run on CPU regardless (no model); the manager records the device the
  session *would* use and tags `ProcessingSession.device`.
- **Logical reservation** via a Redis key `gpu:{index}:owner` (NX + TTL, refreshed by
  heartbeat) + in-process lock, so a future heavy job cannot silently grab the same
  GPU. Released on terminal state / shutdown.
- **VRAM budgeting** interface stub `can_fit(estimated_mb, device)` — CPU always
  fits; CUDA checks measured free VRAM. No model load in Phase 5.
- **Multi-GPU** is interface-only: the API accepts a device index and enumerates
  devices, but scheduling stays single-device.

Verified environment: NVIDIA RTX 3070 Laptop (8 GB), driver 592.00, CUDA 12.8,
`nvidia-smi` present. The GPU-present path and the CPU-fallback path are both tested;
**acceptance does not depend on CUDA**.

## Consequences
Phase 6 plugs real model VRAM estimates into `can_fit`/reservation with no interface
change. The globally-installed PyTorch on this machine is unrelated to the project and
is never imported by the runtime.

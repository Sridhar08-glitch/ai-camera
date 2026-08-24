"""
Detector device policy + truthful execution-provider resolution (Phase 6 / §14).

The runtime must never *pretend* to use a GPU. This module resolves an ONNX
Runtime execution-provider (EP) preference list from (a) the requested policy,
(b) the GPUManager's real device selection, and (c) the EPs actually available in
the installed onnxruntime build. After a session is created, the ACTUAL EP that
ORT chose is recorded back onto the `ResolvedDevice` so callers report reality —
if the CUDA EP is not present, we run on CPU and say so.

No torch, no CUDA import. Pure policy + string resolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DevicePolicy(str, Enum):
    REQUIRE_GPU = "REQUIRE_GPU"   # fail loudly if no CUDA EP is truly available
    PREFER_GPU = "PREFER_GPU"     # use CUDA EP if available, else CPU (honest fallback)
    CPU_ONLY = "CPU_ONLY"         # never attempt GPU

    @classmethod
    def parse(cls, value: str | None) -> "DevicePolicy":
        try:
            return cls((value or "PREFER_GPU").upper())
        except ValueError:
            return cls.PREFER_GPU


class DeviceResolutionError(Exception):
    """REQUIRE_GPU requested but no CUDA execution provider is available."""

    def __init__(self, message: str):
        super().__init__(message)


# ONNX Runtime EP names.
_CUDA_EP = "CUDAExecutionProvider"
_CPU_EP = "CPUExecutionProvider"


@dataclass
class ResolvedDevice:
    """The device decision for a detector session.

    `requested_ep_list` is what we *ask* ORT to use (ordered preference). `actual_ep`
    is filled in AFTER an InferenceSession exists (`ort_session.get_providers()[0]`)
    so reporting is truthful. `gpu_device_tag` mirrors the GPUManager tag.
    """

    policy: DevicePolicy
    gpu_device_tag: str                 # 'cpu' | 'cuda:<idx>'
    requested_ep_list: list[str] = field(default_factory=lambda: [_CPU_EP])
    cuda_available: bool = False        # CUDA EP present in this ORT build?
    actual_ep: str = ""                 # set post-session-creation (truthful)
    note: str = ""

    @property
    def using_gpu(self) -> bool:
        """True only if ORT actually selected the CUDA EP (never a guess)."""
        return self.actual_ep == _CUDA_EP

    def to_dict(self) -> dict:
        return {
            "policy": self.policy.value,
            "gpu_device_tag": self.gpu_device_tag,
            "requested_ep_list": list(self.requested_ep_list),
            "cuda_available": self.cuda_available,
            "actual_ep": self.actual_ep,
            "using_gpu": self.using_gpu,
            "note": self.note,
        }


def available_providers() -> list[str]:
    """EPs the installed onnxruntime build exposes. Empty if ORT is absent."""
    try:
        import onnxruntime as ort
    except Exception:  # pragma: no cover - ORT is a pinned dependency
        return []
    try:
        return list(ort.get_available_providers())
    except Exception:  # pragma: no cover - defensive
        return []


def resolve_device(policy: DevicePolicy, gpu_device_tag: str) -> ResolvedDevice:
    """Turn a policy + GPUManager device tag into a truthful EP preference list.

    Rules:
      * CPU_ONLY                    → [CPU]; never CUDA.
      * PREFER_GPU + CUDA available + cuda:* tag → [CUDA, CPU] (honest fallback).
      * PREFER_GPU otherwise        → [CPU]; note why GPU was skipped.
      * REQUIRE_GPU + not available → raise DeviceResolutionError (no silent CPU).

    "Available" means BOTH the ORT build exposes the CUDA EP AND the GPUManager
    selected a cuda:* device. We do not fabricate GPU usage.
    """
    provs = available_providers()
    cuda_in_build = _CUDA_EP in provs
    gpu_selected = gpu_device_tag.startswith("cuda:")
    cuda_available = cuda_in_build and gpu_selected

    if policy is DevicePolicy.CPU_ONLY:
        return ResolvedDevice(
            policy=policy, gpu_device_tag="cpu", requested_ep_list=[_CPU_EP],
            cuda_available=cuda_available, note="cpu_only policy",
        )

    if policy is DevicePolicy.REQUIRE_GPU:
        if not cuda_available:
            reason = (
                "CUDA execution provider not in onnxruntime build"
                if not cuda_in_build else "no CUDA device selected by GPUManager"
            )
            raise DeviceResolutionError(
                f"REQUIRE_GPU: {reason} (available EPs: {provs or 'none'})"
            )
        return ResolvedDevice(
            policy=policy, gpu_device_tag=gpu_device_tag,
            requested_ep_list=[_CUDA_EP, _CPU_EP], cuda_available=True,
            note="cuda required and available",
        )

    # PREFER_GPU
    if cuda_available:
        return ResolvedDevice(
            policy=policy, gpu_device_tag=gpu_device_tag,
            requested_ep_list=[_CUDA_EP, _CPU_EP], cuda_available=True,
            note="cuda preferred and available",
        )
    reason = (
        "CUDA EP absent from onnxruntime build" if not cuda_in_build
        else "GPUManager selected cpu"
    )
    return ResolvedDevice(
        policy=policy, gpu_device_tag="cpu", requested_ep_list=[_CPU_EP],
        cuda_available=False, note=f"cpu fallback ({reason})",
    )

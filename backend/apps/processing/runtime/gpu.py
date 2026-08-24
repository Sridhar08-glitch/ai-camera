"""
GPU / resource manager (Phase 5 §11/§14 / ADR-027).

Framework-independent: detects NVIDIA devices via `nvidia-smi` (optional), never
imports torch/CUDA, never fabricates a device. Falls back to CPU cleanly. Provides
logical reserve/release (Redis key + in-process) so a future heavy job cannot
silently grab the same GPU. Phase 5 loads NO model — ownership is logical only.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger("processing")


@dataclass
class GPUDevice:
    index: int
    name: str
    memory_total_mb: int | None = None
    memory_used_mb: int | None = None
    memory_free_mb: int | None = None
    driver_version: str = ""


@dataclass
class GPUStatus:
    available: bool
    mode: str  # "cuda" | "cpu"
    devices: list[GPUDevice] = field(default_factory=list)
    detector: str = "nvidia-smi"
    error: str = ""


def _parse_int(v: str) -> int | None:
    v = (v or "").strip()
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def detect_devices(timeout: float = 3.0) -> GPUStatus:
    """Detect real NVIDIA GPUs via nvidia-smi. No nvidia-smi → CPU mode (not an error)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return GPUStatus(available=False, mode="cpu", detector="none")
    try:
        out = subprocess.run(
            [smi, "--query-gpu=index,name,memory.total,memory.used,memory.free,driver_version",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except Exception as exc:  # nvidia-smi present but failed → CPU, recorded
        logger.warning("gpu_detect_failed", error=str(exc)[:120])
        return GPUStatus(available=False, mode="cpu", error=str(exc)[:120])
    if out.returncode != 0:
        return GPUStatus(available=False, mode="cpu", error=(out.stderr or "nvidia-smi error")[:120])

    devices: list[GPUDevice] = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        idx = _parse_int(parts[0])
        if idx is None:
            continue
        devices.append(GPUDevice(
            index=idx, name=parts[1],
            memory_total_mb=_parse_int(parts[2]),
            memory_used_mb=_parse_int(parts[3]),
            memory_free_mb=_parse_int(parts[4]),
            driver_version=parts[5],
        ))
    if not devices:
        return GPUStatus(available=False, mode="cpu", error="no devices parsed")
    return GPUStatus(available=True, mode="cuda", devices=devices)


class GPUManager:
    """Selects a device and holds a logical reservation. CPU-first: Phase 5
    processors run on CPU regardless; the manager records the device a session
    *would* use and prevents accidental GPU contention (interface for Phase 6)."""

    def __init__(self, *, redis_client=None, reservation_ttl: int = 60):
        self._redis = redis_client
        self._ttl = reservation_ttl
        self._reserved_index: int | None = None
        self._reserved_by: str | None = None

    def status(self) -> GPUStatus:
        return detect_devices()

    def select_device(self, preference: str = "auto") -> str:
        """Return a device tag: 'cpu' or 'cuda:<index>'. Honors preference; 'auto'
        picks the first CUDA device if present else cpu. Never fabricates a GPU."""
        pref = (preference or "auto").lower()
        if pref == "cpu":
            return "cpu"
        st = self.status()
        if pref.startswith("cuda"):
            if not st.available:
                logger.warning("gpu_preference_unavailable", preference=pref)
                return "cpu"
            # honor explicit index if valid, else first device
            if ":" in pref:
                try:
                    want = int(pref.split(":", 1)[1])
                    if any(d.index == want for d in st.devices):
                        return f"cuda:{want}"
                except ValueError:
                    pass
            return f"cuda:{st.devices[0].index}"
        # auto
        return f"cuda:{st.devices[0].index}" if st.available else "cpu"

    def reserve(self, device: str, owner: str) -> bool:
        """Take logical ownership of a CUDA device. CPU needs no reservation.
        Returns False if another owner already holds it (Redis NX key)."""
        if not device.startswith("cuda:"):
            self._reserved_index = None
            self._reserved_by = owner
            return True
        index = device.split(":", 1)[1]
        if self._redis is not None:
            key = f"gpu:{index}:owner"
            try:
                ok = self._redis.set(key, owner, nx=True, ex=self._ttl)
                if not ok:
                    holder = self._redis.get(key)
                    if holder != owner:
                        return False
            except Exception as exc:  # Redis down → in-process only, log
                logger.warning("gpu_reserve_redis_failed", error=str(exc)[:120])
        self._reserved_index = int(index)
        self._reserved_by = owner
        return True

    def refresh(self, owner: str) -> None:
        if self._reserved_index is None or self._redis is None:
            return
        try:
            self._redis.set(f"gpu:{self._reserved_index}:owner", owner, ex=self._ttl)
        except Exception:  # pragma: no cover - defensive
            pass

    def release(self, owner: str) -> None:
        if self._reserved_index is not None and self._redis is not None:
            try:
                key = f"gpu:{self._reserved_index}:owner"
                if self._redis.get(key) == owner:
                    self._redis.delete(key)
            except Exception:  # pragma: no cover - defensive
                pass
        self._reserved_index = None
        self._reserved_by = None

    def can_fit(self, estimated_mb: int, device: str) -> bool:
        """VRAM-budget interface (Phase 6 plugs real estimates). CPU always fits;
        CUDA checks measured free VRAM with headroom. No model load in Phase 5."""
        if not device.startswith("cuda:"):
            return True
        index = int(device.split(":", 1)[1])
        st = self.status()
        for d in st.devices:
            if d.index == index and d.memory_free_mb is not None:
                return estimated_mb <= d.memory_free_mb
        return False

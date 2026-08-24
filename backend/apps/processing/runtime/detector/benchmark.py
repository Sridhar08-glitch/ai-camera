"""
Detector benchmark harness (Phase 6 / task #15). INFRASTRUCTURE timing only.

Measures wall-clock throughput and per-stage latency of a detector provider over a
set of synthetic frames. It reports **speed**, never accuracy: there is no mAP /
precision / recall here and none is implied (deterministic frames + the TEST
provider are meaningless as detections). Downloads nothing, trains nothing.

Used for regression-style performance sanity and to exercise the runtime end to
end without real weights.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class BenchmarkReport:
    provider_name: str
    is_test_provider: bool
    frames: int
    width: int
    height: int
    total_seconds: float
    fps: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_detections: int
    stage_means_ms: dict = field(default_factory=dict)
    accuracy_note: str = "SPEED ONLY — no accuracy/mAP/precision/recall measured or implied."

    def to_dict(self) -> dict:
        return {
            "provider_name": self.provider_name,
            "is_test_provider": self.is_test_provider,
            "frames": self.frames,
            "resolution": f"{self.width}x{self.height}",
            "total_seconds": round(self.total_seconds, 4),
            "fps": round(self.fps, 2),
            "latency_ms": {
                "mean": round(self.mean_latency_ms, 3),
                "p50": round(self.p50_latency_ms, 3),
                "p95": round(self.p95_latency_ms, 3),
            },
            "stage_means_ms": {k: round(v, 3) for k, v in self.stage_means_ms.items()},
            "total_detections": self.total_detections,
            "accuracy_note": self.accuracy_note,
        }


def _synthetic_frame(i: int, width: int, height: int) -> np.ndarray:
    """Deterministic, content-varying frame (no external asset needed)."""
    base = (np.arange(height * width * 3, dtype=np.uint8) + i * 7) % 255
    return base.reshape(height, width, 3)


def run_benchmark(provider, *, frames: int = 60, width: int = 1280, height: int = 720) -> BenchmarkReport:
    """Run `provider.detect()` over `frames` synthetic frames and time it.

    The provider must already be loaded. Returns a speed-only report.
    """
    latencies: list[float] = []
    stage_sums: dict[str, float] = {}
    total_dets = 0

    # Warm one frame so first-call setup doesn't skew latency.
    provider.detect(_synthetic_frame(0, width, height))

    t_start = time.perf_counter()
    for i in range(frames):
        frame = _synthetic_frame(i, width, height)
        t0 = time.perf_counter()
        result = provider.detect(frame)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        total_dets += len(result.detections)
        timings = getattr(provider, "last_timings", None)
        if timings:
            for k, v in timings.items():
                stage_sums[k] = stage_sums.get(k, 0.0) + float(v)
    total = time.perf_counter() - t_start

    arr = np.array(latencies) if latencies else np.array([0.0])
    stage_means = {k: v / max(1, frames) for k, v in stage_sums.items()}
    return BenchmarkReport(
        provider_name=getattr(provider, "name", "unknown"),
        is_test_provider=bool(getattr(provider, "is_test_provider", False)),
        frames=frames, width=width, height=height,
        total_seconds=total, fps=(frames / total if total > 0 else 0.0),
        mean_latency_ms=float(arr.mean()),
        p50_latency_ms=float(np.percentile(arr, 50)),
        p95_latency_ms=float(np.percentile(arr, 95)),
        total_detections=total_dets,
        stage_means_ms=stage_means,
    )

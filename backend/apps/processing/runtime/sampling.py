"""
Frame sampling strategies (Phase 5 §15/D5). Deterministic. Runs on FrameMeta
BEFORE any pixel conversion, so un-sampled frames are never converted.

Modes: EVERY_FRAME, EVERY_N, TARGET_FPS. Every accepted frame keeps full source
identity + timestamp (the FrameMeta is unchanged except processed_index).
"""
from __future__ import annotations

from apps.processing.runtime.frames import FrameMeta
from apps.processing.states import SamplingMode


class Sampler:
    """Stateful, deterministic sampler. Call accept(meta) once per decoded frame in
    order; returns True if the frame should be processed."""

    def __init__(self, mode: str, *, n: int = 1, target_fps: float | None = None):
        self.mode = mode
        self.n = max(1, int(n or 1))
        self.target_fps = target_fps
        self._min_interval = (1.0 / target_fps) if (target_fps and target_fps > 0) else None
        self._last_accepted_ts: float | None = None

    def accept(self, meta: FrameMeta) -> bool:
        if self.mode == SamplingMode.EVERY_FRAME:
            return True
        if self.mode == SamplingMode.EVERY_N:
            return (meta.source_frame_index % self.n) == 0
        if self.mode == SamplingMode.TARGET_FPS:
            if self._min_interval is None:
                return True  # no target → behave as every-frame
            ts = meta.timestamp_seconds
            if self._last_accepted_ts is None or (ts - self._last_accepted_ts) >= self._min_interval:
                self._last_accepted_ts = ts
                return True
            return False
        # Unknown mode → conservative: process every frame.
        return True


def build_sampler(params: dict) -> Sampler:
    sampling = (params or {}).get("sampling", {}) or {}
    mode = sampling.get("mode", SamplingMode.EVERY_FRAME)
    return Sampler(mode, n=sampling.get("n", 1), target_fps=sampling.get("target_fps"))

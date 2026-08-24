"""
Infrastructure (no-AI) FrameProcessors for Phase 5 (§16).

NoOpFrameProcessor  — metadata only; NEVER materializes a NumPy array. Proves the
                      lifecycle/decoder/sampler work with zero pixel conversion.
FrameCountProcessor — counts frames and (optionally) exercises the canonical rgb24
                      NumPy path to prove FrameView.as_rgb_ndarray() works.

Neither produces detections, boxes, or any AI output.
"""
from __future__ import annotations

from apps.processing.runtime.frames import FrameView
from apps.processing.runtime.processors.base import (
    ProcessingContext,
    ProcessorResult,
    ProcessorSummary,
)


class NoOpFrameProcessor:
    name = "noop"
    version = "1"

    def __init__(self):
        self._count = 0

    def setup(self, ctx: ProcessingContext) -> None:
        self._count = 0

    def process(self, view: FrameView, ctx: ProcessingContext) -> ProcessorResult:
        # Metadata only — deliberately never calls view.as_rgb_ndarray().
        self._count += 1
        return ProcessorResult(frame_index=view.meta.source_frame_index,
                               pts_seconds=view.meta.pts_seconds)

    def teardown(self) -> ProcessorSummary:
        return ProcessorSummary(self.name, self.version, self._count)


class FrameCountProcessor:
    name = "framecount"
    version = "1"

    def __init__(self, *, touch_pixels: bool = True):
        self._count = 0
        self._checksum = 0
        self._touch = touch_pixels

    def setup(self, ctx: ProcessingContext) -> None:
        self._count = 0
        self._checksum = 0

    def process(self, view: FrameView, ctx: ProcessingContext) -> ProcessorResult:
        self._count += 1
        note = ""
        if self._touch:
            # Exercise the canonical rgb24 NumPy path (proves as_rgb_ndarray()).
            arr = view.as_rgb_ndarray()
            # Cheap deterministic reduction — NOT detection.
            s = int(arr[:: max(1, arr.shape[0] // 8), :: max(1, arr.shape[1] // 8), 0].sum())
            self._checksum = (self._checksum + s) & 0xFFFFFFFF
            note = f"rgb{arr.shape[1]}x{arr.shape[0]}"
        return ProcessorResult(frame_index=view.meta.source_frame_index,
                               pts_seconds=view.meta.pts_seconds, note=note)

    def teardown(self) -> ProcessorSummary:
        return ProcessorSummary(self.name, self.version, self._count,
                               extra={"pixel_checksum": self._checksum})


def _build_detector():
    # Imported lazily: the detector module pulls in the detector runtime + governance
    # models; keep infra import (used by params validation) lightweight and free of
    # any app-registry ordering concerns.
    from apps.processing.runtime.processors.detection import DetectionFrameProcessor

    return DetectionFrameProcessor()


# name → zero-arg builder returning a fresh processor instance.
_REGISTRY = {
    NoOpFrameProcessor.name: NoOpFrameProcessor,
    FrameCountProcessor.name: FrameCountProcessor,
    "detector": _build_detector,
}


def build_processor(name: str):
    entry = _REGISTRY.get(name or NoOpFrameProcessor.name)
    if entry is None:
        raise ValueError(f"unknown processor '{name}'")
    return entry()

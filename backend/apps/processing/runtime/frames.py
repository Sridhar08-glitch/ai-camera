"""
Frame identity, timestamps, and the lazy frame-access wrapper (Phase 5 §14/§16, D10).

FrameMeta carries reliable source identity (index + PTS-derived timestamp). FrameView
wraps a raw PyAV VideoFrame and exposes NumPy conversion lazily and cached — the
canonical representation is rgb24 (H×W×3, uint8, C-contiguous). NoOp processors read
only metadata and never trigger a conversion; pixel processors call as_rgb_ndarray().
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # avoid importing numpy/av at module import time
    import av
    import numpy as np

CANONICAL_FORMAT = "rgb24"


@dataclass
class FrameMeta:
    """Per-frame identity. `pts_seconds` is authoritative time when PTS exists;
    `approx_seconds` (index/fps) is a labeled fallback only. `processed_index` is
    set by the sampler when a frame is accepted (-1 until then)."""

    source_frame_index: int          # 0-based decode order from stream start
    decoded_index: int               # count of frames decoded this run
    processed_index: int             # count of frames that passed the sampler
    pts: Optional[int]
    time_base: Optional[Fraction]
    pts_seconds: Optional[float]
    approx_seconds: float

    @property
    def timestamp_seconds(self) -> float:
        """Best available source timestamp: real PTS if present, else fallback."""
        return self.pts_seconds if self.pts_seconds is not None else self.approx_seconds


def compute_pts_seconds(pts, time_base) -> Optional[float]:
    if pts is None or time_base is None:
        return None
    return float(pts * time_base)


class FrameView:
    """Lazy wrapper: raw PyAV frame + FrameMeta, with cached rgb24 ndarray access.

    The pipeline passes this to every FrameProcessor. Conversion happens only when
    a processor asks, at most once per (frame, format), and is cached only for the
    lifetime of this view (dropped after process(), keeping memory bounded).
    """

    __slots__ = ("frame", "meta", "_cache")

    def __init__(self, frame: "av.VideoFrame", meta: FrameMeta):
        self.frame = frame
        self.meta = meta
        self._cache: dict[str, "np.ndarray"] = {}

    def as_rgb_ndarray(self) -> "np.ndarray":
        """Canonical representation: rgb24, H×W×3, uint8, C-contiguous. Cached."""
        return self.as_ndarray(CANONICAL_FORMAT)

    def as_ndarray(self, fmt: str) -> "np.ndarray":
        """Return the frame as a NumPy array in `fmt` (default caller: rgb24).

        Escape hatch for a processor with a strong reason to want another format.
        Cached per format; the swscale copy runs exactly once per format."""
        cached = self._cache.get(fmt)
        if cached is None:
            cached = self.frame.to_ndarray(format=fmt)
            self._cache[fmt] = cached
        return cached

    @property
    def converted(self) -> bool:
        """True if a NumPy array was materialized for this frame (test/introspection)."""
        return bool(self._cache)

    def release(self) -> None:
        """Drop the raw frame and any cached array so memory stays bounded."""
        self._cache.clear()
        self.frame = None  # type: ignore[assignment]

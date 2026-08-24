"""
DetectorProvider contract (Phase 6 / §23, D10).

A provider is the framework boundary: it loads a model, warms it up, and turns an
rgb24 frame into a framework-independent `DetectionResult` (canonical normalized
XYXY). The CV runtime — never Django/Celery — owns the load. Providers are loaded
once per session, reused across frames, and unloaded on teardown.

The Protocol is deliberately framework-neutral: an ONNX-backed provider and the
deterministic TEST provider both satisfy it without exposing tensors or ORT/torch
types to callers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from apps.processing.runtime.detector.contract import DetectionResult

if TYPE_CHECKING:  # avoid importing numpy at module import time
    import numpy as np

    from apps.processing.runtime.detector.device import ResolvedDevice


@runtime_checkable
class DetectorProvider(Protocol):
    """Framework boundary for a single-frame object detector.

    Lifecycle: load() → warmup() → (preprocess/infer/postprocess)* → unload().
    `detect()` is the convenience path the processor uses per frame; it composes
    the three stages so timing can be measured around each.
    """

    name: str
    version: str
    is_test_provider: bool

    def load(self, device: "ResolvedDevice") -> None:
        """Acquire the model on the resolved device. Idempotent per instance."""
        ...

    def warmup(self) -> None:
        """Optional: run a throwaway inference so the first real frame is not slow."""
        ...

    def classes(self) -> list[int]:
        """Canonical taxonomy class ids this provider can emit."""
        ...

    def detect(self, rgb: "np.ndarray") -> DetectionResult:
        """Full path: preprocess → infer → postprocess for one rgb24 frame."""
        ...

    def unload(self) -> None:
        """Release the model + any device memory. Safe to call more than once."""
        ...

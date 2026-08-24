"""
FrameProcessor contract (Phase 5 §16/D10). No AI, no detection.

The pipeline passes a FrameView (lazy raw frame + FrameMeta). Phase 5 ships only
infrastructure processors. Phase 6 adds a detector implementing the SAME Protocol
by calling view.as_rgb_ndarray() — no pipeline redesign.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

from apps.processing.runtime.frames import FrameView


@dataclass
class ProcessingContext:
    snapshot_payload: dict
    params: dict
    device: str
    logger: Any = None
    # Phase 6: identity a persisting processor (e.g. the detector) needs to write
    # durable per-frame rows traceable to the session/video. Infra processors ignore.
    session_id: Any = None
    video_id: Any = None


@dataclass
class ProcessorResult:
    frame_index: int
    pts_seconds: Optional[float]
    note: str = ""


@dataclass
class ProcessorSummary:
    name: str
    version: str
    frames_processed: int
    extra: dict = field(default_factory=dict)


@runtime_checkable
class FrameProcessor(Protocol):
    name: str
    version: str

    def setup(self, ctx: ProcessingContext) -> None: ...
    def process(self, view: FrameView, ctx: ProcessingContext) -> ProcessorResult: ...
    def teardown(self) -> ProcessorSummary: ...

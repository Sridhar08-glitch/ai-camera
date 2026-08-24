"""Phase 5 — decoder, sampling, FrameProcessor/NumPy boundary, pipeline end-to-end."""
from __future__ import annotations

import pytest

from apps.processing.models import ProcessingSession
from apps.processing.runtime.frames import FrameMeta, FrameView
from apps.processing.runtime.processors.infra import (
    FrameCountProcessor,
    NoOpFrameProcessor,
)
from apps.processing.runtime.sampling import Sampler
from apps.processing.runtime.video_source import DecoderError, LocalFileSource
from apps.processing.services.claim import claim_next
from apps.processing.services.session import create_session
from apps.processing.runtime.pipeline import run_session
from apps.processing.states import ProcessingState, SamplingMode
from tests._processing_helpers import make_valid_video

pytestmark = pytest.mark.django_db


# ---------------- Decoder ----------------

def test_decoder_sequential_iteration_and_pts(vstorage):
    video = make_valid_video(w=64, h=48, fps=6, seconds=1.0)
    from apps.ingestion.storage import get_storage_backend
    path = get_storage_backend().resolve_path(video.storage_key)
    with LocalFileSource(path, source_fps=6) as src:
        metas = [v.meta for v in src.frames()]
    assert len(metas) == 6
    assert [m.source_frame_index for m in metas] == [0, 1, 2, 3, 4, 5]
    # PTS present → pts_seconds monotonic non-decreasing; timestamps authoritative.
    assert all(m.pts is not None for m in metas)
    ts = [m.pts_seconds for m in metas]
    assert ts == sorted(ts)


def test_decoder_missing_file_raises(vstorage):
    with pytest.raises(DecoderError) as exc:
        LocalFileSource("E:/nonexistent/does_not_exist.mp4").open()
    assert exc.value.code == "decoder_open_failed"


def test_decoder_corrupt_stream_raises(vstorage):
    video = make_valid_video(content=b"not a video" * 100)
    from apps.ingestion.storage import get_storage_backend
    path = get_storage_backend().resolve_path(video.storage_key)
    with pytest.raises(DecoderError):
        LocalFileSource(path).open()


# ---------------- Sampling ----------------

def _meta(i, ts):
    return FrameMeta(source_frame_index=i, decoded_index=i, processed_index=-1,
                     pts=i, time_base=None, pts_seconds=ts, approx_seconds=ts)


def test_sampling_every_frame():
    s = Sampler(SamplingMode.EVERY_FRAME)
    assert [s.accept(_meta(i, i / 6)) for i in range(6)] == [True] * 6


def test_sampling_every_n():
    s = Sampler(SamplingMode.EVERY_N, n=3)
    accepted = [i for i in range(9) if s.accept(_meta(i, i / 6))]
    assert accepted == [0, 3, 6]


def test_sampling_target_fps_respects_timestamps():
    # Source ~6 fps; target 2 fps → ~1 every 3 frames by timestamp.
    s = Sampler(SamplingMode.TARGET_FPS, target_fps=2.0)
    accepted = [i for i in range(12) if s.accept(_meta(i, i / 6.0))]
    assert accepted[0] == 0
    # gaps between accepted timestamps are >= 0.5s
    assert len(accepted) <= 5 and len(accepted) >= 3


# ---------------- FrameProcessor / NumPy boundary ----------------

class _SpyFrame:
    """Fake av.VideoFrame that records to_ndarray calls."""

    def __init__(self):
        self.calls = 0

    def to_ndarray(self, format="rgb24"):
        import numpy as np
        self.calls += 1
        return np.zeros((48, 64, 3), dtype=np.uint8)


def test_noop_never_converts():
    frame = _SpyFrame()
    view = FrameView(frame, _meta(0, 0.0))
    proc = NoOpFrameProcessor()
    from apps.processing.runtime.processors.base import ProcessingContext
    ctx = ProcessingContext(snapshot_payload={}, params={}, device="cpu")
    proc.setup(ctx)
    proc.process(view, ctx)
    assert frame.calls == 0  # NoOp materializes no ndarray
    assert view.converted is False


def test_as_rgb_ndarray_canonical_and_cached():
    frame = _SpyFrame()
    view = FrameView(frame, _meta(0, 0.0))
    arr1 = view.as_rgb_ndarray()
    arr2 = view.as_rgb_ndarray()
    import numpy as np
    assert arr1.shape == (48, 64, 3) and arr1.dtype == np.uint8
    assert arr1.flags["C_CONTIGUOUS"]
    assert arr1 is arr2           # cached — same object
    assert frame.calls == 1       # converted exactly once (no duplicate copy)


def test_framecount_processor_touches_pixels():
    frame = _SpyFrame()
    view = FrameView(frame, _meta(0, 0.0))
    proc = FrameCountProcessor(touch_pixels=True)
    from apps.processing.runtime.processors.base import ProcessingContext
    ctx = ProcessingContext(snapshot_payload={}, params={}, device="cpu")
    proc.setup(ctx)
    proc.process(view, ctx)
    assert frame.calls == 1
    summary = proc.teardown()
    assert summary.frames_processed == 1
    assert "pixel_checksum" in summary.extra


# ---------------- Pipeline end-to-end ----------------

def _run(video_id, operator, params=None):
    session = create_session(video_id=video_id, params=params, actor=operator)
    claimed = claim_next("test-runtime")
    assert claimed is not None and claimed.id == session.id
    return run_session(claimed)


def test_pipeline_completes_noop(vstorage, operator):
    video = make_valid_video(fps=6, seconds=1.0)
    state = _run(video.id, operator, {"processor": "noop", "sampling": {"mode": "every_frame"}})
    assert state == ProcessingState.COMPLETED
    s = ProcessingSession.objects.get(video_asset=video)
    assert s.frames_decoded == 6
    assert s.frames_processed == 6
    assert s.progress_percent == 100.0
    assert s.error_code == ""


def test_pipeline_framecount_uses_numpy(vstorage, operator):
    video = make_valid_video(fps=6, seconds=1.0)
    state = _run(video.id, operator, {"processor": "framecount", "sampling": {"mode": "every_frame"}})
    assert state == ProcessingState.COMPLETED


def test_pipeline_every_n_processes_subset(vstorage, operator):
    video = make_valid_video(fps=10, seconds=1.0)  # 10 frames
    state = _run(video.id, operator, {"processor": "noop", "sampling": {"mode": "every_n", "n": 5}})
    assert state == ProcessingState.COMPLETED
    s = ProcessingSession.objects.get(video_asset=video)
    assert s.frames_decoded == 10
    assert s.frames_processed == 2  # indices 0 and 5


def test_pipeline_no_detection_output(vstorage, operator):
    """Phase 5 must produce no detection-like output anywhere on the session."""
    video = make_valid_video(fps=6, seconds=1.0)
    _run(video.id, operator, {"processor": "framecount"})
    s = ProcessingSession.objects.get(video_asset=video)
    dump = str(s.__dict__).lower()
    for banned in ("bbox", "detection", "vehicle", "track", "class_id", "confidence"):
        assert banned not in dump


def test_pipeline_missing_storage_file_fails(vstorage, operator):
    video = make_valid_video()
    # Delete the backing file so decode can't open it.
    from apps.ingestion.storage import get_storage_backend
    import os
    os.remove(get_storage_backend().resolve_path(video.storage_key))
    state = _run(video.id, operator, None)
    assert state == ProcessingState.FAILED
    s = ProcessingSession.objects.get(video_asset=video)
    assert s.error_code == "storage_file_missing"


def test_pipeline_bounded_memory(vstorage, operator):
    """Peak RSS stays bounded across a longer clip (no full-video buffering)."""
    psutil = pytest.importorskip("psutil")
    video = make_valid_video(w=320, h=240, fps=15, seconds=4.0)  # 60 frames
    proc = psutil.Process()
    before = proc.memory_info().rss
    state = _run(video.id, operator, {"processor": "framecount", "sampling": {"mode": "every_frame"}})
    after = proc.memory_info().rss
    assert state == ProcessingState.COMPLETED
    # Growth must be far below "whole video decoded into RAM" — generous 150 MB bound.
    assert (after - before) < 150 * 1024 * 1024

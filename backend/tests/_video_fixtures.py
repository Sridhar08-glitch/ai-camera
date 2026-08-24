"""Deterministic tiny-video fixture helpers for Phase 4 tests (PyAV-generated, no numpy)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def make_test_video(path: str, *, w: int = 64, h: int = 48, fps: int = 6, seconds: float = 1.0) -> str:
    """Encode a tiny valid MP4 (mpeg4 codec — LGPL, always available) to `path`.

    Frames are sourced from the built-in lavfi 'testsrc' generator, so no numpy or
    external assets are required.
    """
    import av

    src = av.open(f"testsrc=duration={seconds}:size={w}x{h}:rate={fps}", format="lavfi")
    out = av.open(path, "w")
    try:
        ostream = out.add_stream("mpeg4", rate=fps)
        ostream.width = w
        ostream.height = h
        ostream.pix_fmt = "yuv420p"
        for frame in src.decode(video=0):
            for packet in ostream.encode(frame):
                out.mux(packet)
        for packet in ostream.encode():
            out.mux(packet)
    finally:
        out.close()
        src.close()
    return path


def make_test_video_bytes(**kw) -> bytes:
    fd, name = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)  # avoid Windows file-lock; PyAV reopens by path
    tmp = Path(name)
    try:
        make_test_video(str(tmp), **kw)
        return tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)

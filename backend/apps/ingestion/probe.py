"""
Video validation, metadata probing, and single-frame thumbnail (Phase 4 / ADR-023).

PyAV-only, strictly scoped to ingestion: readability check + basic metadata +
one thumbnail. NO frame iteration/sampling/processing (that is Phase 5).
No fake fallback — if the decoder is unavailable or the file is unreadable, we
raise a clear error and the asset is never marked valid.
"""
from __future__ import annotations

import io
from dataclasses import dataclass


class ProbeError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


# Container signature (magic-byte) sniffing — advisory pre-decode gate.
# For MP4/MOV the 'ftyp' box appears at offset 4.
def sniff_container(header: bytes) -> str | None:
    if len(header) < 12:
        return None
    if header[4:8] == b"ftyp":
        return "mp4"  # covers mp4/mov/m4v family
    if header[:4] == b"\x1aE\xdf\xa3":
        return "matroska"  # mkv/webm
    if header[:4] == b"RIFF" and header[8:12] == b"AVI ":
        return "avi"
    return None


def decoder_available() -> tuple[bool, str]:
    try:
        import av

        return True, av.__version__
    except Exception as exc:  # pragma: no cover - environment guard
        return False, str(exc)[:120]


@dataclass
class VideoMetadata:
    container_format: str
    codec: str
    duration_s: float | None
    width: int | None
    height: int | None
    fps: float | None
    frame_count: int | None


def probe_video(path: str) -> VideoMetadata:
    """Open the file and extract basic metadata. Raises ProbeError on failure."""
    try:
        import av
    except Exception as exc:
        raise ProbeError("decoder_unavailable", str(exc)) from exc

    try:
        container = av.open(path)
    except Exception as exc:
        raise ProbeError("corrupt_video", f"cannot open: {exc}") from exc

    try:
        if not container.streams.video:
            raise ProbeError("unsupported_video", "no video stream")
        s = container.streams.video[0]
        cc = s.codec_context
        fps = float(s.average_rate) if s.average_rate else None
        duration = None
        if s.duration is not None and s.time_base:
            duration = float(s.duration * s.time_base)
        elif container.duration is not None:
            duration = float(container.duration) / 1_000_000  # AV_TIME_BASE
        frames = s.frames or None  # best-effort; may be 0/inaccurate for VBR
        return VideoMetadata(
            container_format=(container.format.name or "").split(",")[0],
            codec=cc.name or "",
            duration_s=duration,
            width=cc.width or None,
            height=cc.height or None,
            fps=fps,
            frame_count=frames,
        )
    except ProbeError:
        raise
    except Exception as exc:
        raise ProbeError("corrupt_video", str(exc)) from exc
    finally:
        container.close()


def make_thumbnail(path: str, max_dim: int = 640) -> bytes:
    """Decode ONE frame and return JPEG bytes (no Pillow; PyAV mjpeg). Raises ProbeError."""
    try:
        import av
    except Exception as exc:
        raise ProbeError("decoder_unavailable", str(exc)) from exc

    try:
        container = av.open(path)
    except Exception as exc:
        raise ProbeError("corrupt_video", f"cannot open: {exc}") from exc
    try:
        stream = container.streams.video[0]
        frame = None
        for f in container.decode(stream):  # first available frame only
            frame = f
            break
        if frame is None:
            raise ProbeError("corrupt_video", "no decodable frame")
        w, h = frame.width, frame.height
        scale = min(max_dim / max(w, h), 1.0)
        tw, th = max(2, int(w * scale) // 2 * 2), max(2, int(h * scale) // 2 * 2)
        out = io.BytesIO()
        oc = av.open(out, "w", format="mjpeg")
        try:
            st = oc.add_stream("mjpeg")
            st.width, st.height, st.pix_fmt = tw, th, "yuvj420p"
            reframed = frame.reformat(width=tw, height=th, format="yuvj420p")
            for packet in st.encode(reframed):
                oc.mux(packet)
            for packet in st.encode():
                oc.mux(packet)
        finally:
            oc.close()
        return out.getvalue()
    except ProbeError:
        raise
    except Exception as exc:
        raise ProbeError("corrupt_video", str(exc)) from exc
    finally:
        container.close()

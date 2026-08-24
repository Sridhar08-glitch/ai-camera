"""
VideoSource abstraction + LocalFileSource over PyAV (Phase 5 §12/§13/D4).

Frozen provider interface: open() / frames() -> Iterator[FrameView] / metadata() /
close(). Sequential decode only (no seeking in Phase 5). Real PTS is preserved;
mid-stream corrupt frames are skipped and counted (never silently). Resource
cleanup is guaranteed via close()/context manager.
"""
from __future__ import annotations

from typing import Iterator, Optional

import structlog

from apps.processing.runtime.frames import FrameMeta, FrameView, compute_pts_seconds

logger = structlog.get_logger("processing")


class DecoderError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


class VideoSourceMetadata:
    __slots__ = ("fps", "duration_s", "width", "height", "time_base")

    def __init__(self, *, fps, duration_s, width, height, time_base):
        self.fps = fps
        self.duration_s = duration_s
        self.width = width
        self.height = height
        self.time_base = time_base


class LocalFileSource:
    """Decode a locally-stored video file sequentially with PyAV.

    `corrupt_frames` counts decode errors skipped mid-stream. If the stream cannot
    be opened at all → DecoderError('decoder_open_failed'). If PyAV/libav is not
    importable → DecoderError('decoder_unavailable').
    """

    def __init__(self, path: str, *, source_fps: Optional[float] = None):
        self._path = path
        self._source_fps = source_fps
        self._container = None
        self._stream = None
        self.corrupt_frames = 0

    def open(self) -> "LocalFileSource":
        try:
            import av
        except Exception as exc:  # pragma: no cover - env-specific
            raise DecoderError("decoder_unavailable", str(exc)) from exc
        try:
            self._container = av.open(self._path)
        except Exception as exc:
            raise DecoderError("decoder_open_failed", str(exc)) from exc
        if not self._container.streams.video:
            self.close()
            raise DecoderError("decoder_open_failed", "no video stream")
        self._stream = self._container.streams.video[0]
        return self

    def metadata(self) -> VideoSourceMetadata:
        s = self._stream
        cc = s.codec_context
        fps = float(s.average_rate) if s.average_rate else self._source_fps
        duration = None
        if s.duration is not None and s.time_base:
            duration = float(s.duration * s.time_base)
        elif self._container.duration is not None:
            duration = float(self._container.duration) / 1_000_000
        return VideoSourceMetadata(
            fps=fps, duration_s=duration,
            width=cc.width or None, height=cc.height or None,
            time_base=s.time_base,
        )

    def frames(self) -> Iterator[FrameView]:
        """Yield a FrameView per successfully decoded frame, in source order.

        Sequential PyAV decode. Per-frame decode errors are skipped + counted
        (frozen §33), not fatal, unless nothing decodes.
        """
        if self._container is None:
            raise DecoderError("decoder_open_failed", "source not opened")
        source_fps = None
        try:
            source_fps = float(self._stream.average_rate) if self._stream.average_rate else self._source_fps
        except Exception:
            source_fps = self._source_fps
        time_base = self._stream.time_base

        source_index = 0
        decoded = 0
        packet_iter = self._container.demux(self._stream)
        while True:
            try:
                packet = next(packet_iter)
            except StopIteration:
                break
            except Exception as exc:  # demux-level corruption
                self.corrupt_frames += 1
                logger.warning("processing_demux_error", error=str(exc)[:120])
                continue
            try:
                decoded_frames = list(packet.decode())
            except Exception as exc:  # mid-stream corrupt frame — skip + count
                self.corrupt_frames += 1
                logger.warning("processing_corrupt_frame", error=str(exc)[:120])
                continue
            for frame in decoded_frames:
                pts_seconds = compute_pts_seconds(frame.pts, time_base)
                approx = (source_index / source_fps) if source_fps else float(source_index)
                meta = FrameMeta(
                    source_frame_index=source_index,
                    decoded_index=decoded,
                    processed_index=-1,  # set by the sampler when accepted
                    pts=frame.pts,
                    time_base=time_base,
                    pts_seconds=pts_seconds,
                    approx_seconds=approx,
                )
                yield FrameView(frame, meta)
                source_index += 1
                decoded += 1

    def close(self) -> None:
        if self._container is not None:
            try:
                self._container.close()
            except Exception:  # pragma: no cover - defensive
                pass
            self._container = None
            self._stream = None

    def __enter__(self) -> "LocalFileSource":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

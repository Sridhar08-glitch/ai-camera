"""
DetectionFrameProcessor (Phase 6 / §24). Implements the Phase 5 FrameProcessor
Protocol — no pipeline redesign. It is the ONLY place a detection model is loaded.

Lifecycle:
  setup()    resolve + load the provider once (governed ONNX or TEST provider),
             bind the device policy, prepare a bounded persist buffer.
  process()  view.as_rgb_ndarray() → provider.detect() → buffer a FrameDetectionBatch
             row; flush in bulk every N frames (never a per-frame DB write).
  teardown() flush the tail, unload the model, return a summary.

Empty detections are a valid result, never a failure. A per-frame inference error
is recorded (metric + summary) and skipped so one bad frame can't fail the session;
load-time failures are fatal (the session cannot run without a provider).
"""
from __future__ import annotations

import time

import structlog

from apps.processing import observability
from apps.processing.runtime.detector.contract import DetectionError
from apps.processing.runtime.detector.device import DeviceResolutionError
from apps.processing.runtime.detector.factory import build_provider
from apps.processing.runtime.frames import FrameView
from apps.processing.runtime.processors.base import (
    ProcessingContext,
    ProcessorResult,
    ProcessorSummary,
)
from apps.processing.taxonomy import TAXONOMY_VERSION

logger = structlog.get_logger("processing")


class DetectionFrameProcessor:
    name = "detector"
    version = "1"

    def __init__(self):
        self._provider = None
        self._resolved = None
        self._session_id = None
        self._video_id = None
        self._model_version = None
        self._provider_kind = "test"
        self._persist_every_n = 50
        self._buffer: list = []
        self._frames = 0
        self._detections_total = 0
        self._infer_failures = 0

    # ---- setup: resolve + load provider ONCE ----
    def setup(self, ctx: ProcessingContext) -> None:
        from django.conf import settings

        self._session_id = ctx.session_id
        self._video_id = ctx.video_id
        self._persist_every_n = max(1, int(settings.CV_DETECTOR_PERSIST_EVERY_N))

        detector_params = (ctx.params or {}).get("detector", {}) or {}
        try:
            resolved = build_provider(detector_params, ctx.device)
        except DeviceResolutionError as exc:
            observability.record_detector_failure("device_unavailable")
            raise DetectionError("device_unavailable", str(exc)) from exc
        except DetectionError as exc:
            observability.record_detector_failure(exc.code)
            raise

        self._resolved = resolved
        self._provider = resolved.provider
        self._model_version = resolved.model_version
        self._provider_kind = "test" if resolved.is_test_provider else "onnx"
        logger.info(
            "detector_setup",
            provider=self._provider.name,
            is_test_provider=resolved.is_test_provider,
            actual_ep=resolved.device.actual_ep,
            using_gpu=resolved.device.using_gpu,
        )

    # ---- per-frame: detect + buffer ----
    def process(self, view: FrameView, ctx: ProcessingContext) -> ProcessorResult:
        meta = view.meta
        rgb = view.as_rgb_ndarray()
        try:
            result = self._provider.detect(rgb)
            result.validate()
        except (DetectionError, ValueError) as exc:
            # Skip a single bad frame; the session continues (empty != failure).
            self._infer_failures += 1
            code = getattr(exc, "code", "inference_failed")
            observability.record_detector_failure(code)
            logger.warning("detector_frame_failed", frame=meta.source_frame_index, code=code)
            return ProcessorResult(frame_index=meta.source_frame_index,
                                   pts_seconds=meta.pts_seconds, note="detect_error")

        timings = getattr(self._provider, "last_timings", None)
        if timings:
            observability.observe_detector_stages(timings, self._provider_kind)
        observability.record_detection_frame(self._provider_kind)

        self._frames += 1
        self._detections_total += len(result.detections)
        self._buffer.append(self._build_row(meta, result))
        if len(self._buffer) >= self._persist_every_n:
            self._flush()

        return ProcessorResult(frame_index=meta.source_frame_index,
                               pts_seconds=meta.pts_seconds,
                               note=f"det={len(result.detections)}")

    def _build_row(self, meta, result):
        from apps.processing.models import FrameDetectionBatch

        return FrameDetectionBatch(
            session_id=self._session_id,
            video_id=self._video_id,
            model_version=self._model_version,
            provider_name=result.provider_name,
            provider_version=result.provider_version,
            is_test_provider=result.is_test_provider,
            taxonomy_version=TAXONOMY_VERSION,
            source_frame_index=meta.source_frame_index,
            pts_seconds=meta.pts_seconds,
            detection_count=len(result.detections),
            detections=result.to_payload(),
        )

    def _flush(self) -> None:
        if not self._buffer:
            return
        from apps.processing.models import FrameDetectionBatch

        t0 = time.perf_counter()
        # ignore_conflicts: a re-run over an already-persisted frame is a no-op,
        # never a hard failure (unique on session+frame).
        FrameDetectionBatch.objects.bulk_create(self._buffer, ignore_conflicts=True)
        observability.observe_detector_persist_ms((time.perf_counter() - t0) * 1000.0)
        self._buffer.clear()

    # ---- teardown: flush tail + unload ----
    def teardown(self) -> ProcessorSummary:
        self._flush()
        provider_name = "unknown"
        provider_version = ""
        if self._provider is not None:
            provider_name = self._provider.name
            provider_version = getattr(self._provider, "version", "")
            try:
                self._provider.unload()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("detector_unload_failed", error=str(exc)[:120])
        extra = {
            "provider_name": provider_name,
            "provider_version": provider_version,
            "is_test_provider": self._provider_kind == "test",
            "detections_total": self._detections_total,
            "inference_failures": self._infer_failures,
            "taxonomy_version": TAXONOMY_VERSION,
        }
        if self._resolved is not None:
            extra["device"] = self._resolved.device.to_dict()
        return ProcessorSummary(self.name, self.version, self._frames, extra=extra)

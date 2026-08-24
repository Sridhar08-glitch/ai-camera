"""
Processing metrics registered into the observability allowlist (Phase 5 §28).

Counters/summaries only. NO session_id / video_id / user_id labels — per-session
detail lives on the ProcessingSession row and the API. `outcome` is a small
bounded label set.
"""
from __future__ import annotations

from apps.observability import collectors

collectors.ALLOWED.update({
    "processing_sessions_requested_total": (collectors.COUNTER, "count", "django", frozenset()),
    "processing_sessions_finished_total": (
        collectors.COUNTER, "count", "cv_runtime", frozenset({"outcome"}),
    ),
    "processing_session_duration_ms": (collectors.SUMMARY, "ms", "cv_runtime", frozenset()),
    "processing_decode_fps": (collectors.SUMMARY, "fps", "cv_runtime", frozenset()),
    "processing_throughput_fps": (collectors.SUMMARY, "fps", "cv_runtime", frozenset()),
    "cv_runtime_heartbeat_age_seconds": (collectors.SUMMARY, "s", "celery", frozenset()),
    # Phase 6 detector stage timings + counters. No session/video/model labels —
    # per-session detail lives on the session row + detections API. `provider_kind`
    # is a bounded label ("test" | "onnx"). Failures carry a bounded `code`.
    "detector_preprocess_ms": (collectors.SUMMARY, "ms", "cv_runtime", frozenset({"provider_kind"})),
    "detector_inference_ms": (collectors.SUMMARY, "ms", "cv_runtime", frozenset({"provider_kind"})),
    "detector_postprocess_ms": (collectors.SUMMARY, "ms", "cv_runtime", frozenset({"provider_kind"})),
    "detector_persist_ms": (collectors.SUMMARY, "ms", "cv_runtime", frozenset()),
    "detection_frames_total": (collectors.COUNTER, "count", "cv_runtime", frozenset({"provider_kind"})),
    "detector_failures_total": (collectors.COUNTER, "count", "cv_runtime", frozenset({"code"})),
})


def record_requested() -> None:
    collectors.incr("processing_sessions_requested_total")


def record_finished(outcome: str) -> None:
    collectors.incr("processing_sessions_finished_total", {"outcome": outcome})


def observe_duration_ms(ms: float) -> None:
    collectors.observe("processing_session_duration_ms", ms)


def observe_decode_fps(fps: float) -> None:
    collectors.observe("processing_decode_fps", fps)


def observe_throughput_fps(fps: float) -> None:
    collectors.observe("processing_throughput_fps", fps)


# --- Phase 6 detector metrics ---
def observe_detector_stages(timings: dict, provider_kind: str) -> None:
    """Record preprocess/inference/postprocess ms for a frame (keys optional)."""
    labels = {"provider_kind": provider_kind}
    for key, metric in (
        ("preprocess_ms", "detector_preprocess_ms"),
        ("inference_ms", "detector_inference_ms"),
        ("postprocess_ms", "detector_postprocess_ms"),
    ):
        if key in timings:
            collectors.observe(metric, float(timings[key]), labels)


def observe_detector_persist_ms(ms: float) -> None:
    collectors.observe("detector_persist_ms", ms)


def record_detection_frame(provider_kind: str) -> None:
    collectors.incr("detection_frames_total", {"provider_kind": provider_kind})


def record_detector_failure(code: str) -> None:
    collectors.incr("detector_failures_total", {"code": code})

"""
ONNX Runtime detector backend (Phase 6 / ADR-028, ADR-032).

`OnnxDetector` is the production inference boundary: it loads a *validated* ONNX
container into an `onnxruntime.InferenceSession` with a device-policy-derived
execution-provider list, records the EP ORT actually chose (truthful), runs a
frame, and hands the decoded output to the framework-independent postprocess.

Guardrails: loads ONLY validated ONNX (never a pickle); imports no torch; owns the
model for the CV runtime only; is loaded once and released on unload().

Output contract (`phase6-infra-v1`): the model emits a float array shaped (N,6) or
(1,N,6) = [x1, y1, x2, y2, score, model_class_idx] in letterbox target-pixel space.
Raw single-tensor YOLO-head decoding is a Phase 6T concern and does not change this
module's coordinate/postprocess contract.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

import numpy as np
import structlog

from apps.processing.runtime.detector.contract import DetectionError, DetectionResult
from apps.processing.runtime.detector.device import ResolvedDevice
from apps.processing.runtime.detector.postprocess import postprocess
from apps.processing.runtime.detector.preprocess import letterbox

logger = structlog.get_logger("processing")

OUTPUT_SCHEMA = "phase6-infra-v1"


def _decode_output(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decode a `phase6-infra-v1` output into (boxes_xyxy_target, scores, class_ids)."""
    arr = np.asarray(raw)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 2 or arr.shape[1] != 6:
        raise DetectionError("invalid_output", f"expected (N,6) output, got {arr.shape}")
    boxes = arr[:, 0:4].astype(np.float64)
    scores = arr[:, 4].astype(np.float64)
    class_ids = arr[:, 5].astype(np.int64)
    return boxes, scores, class_ids


class OnnxDetector:
    """Single-frame ONNX detector. Framework boundary — emits only DetectionResult."""

    is_test_provider = False

    def __init__(
        self,
        *,
        onnx_path: str,
        class_map: dict[int, int],
        provider_name: str,
        provider_version: str,
        input_size: int,
        conf_threshold: float,
        iou_threshold: float,
        max_detections: int,
        output_schema: str = OUTPUT_SCHEMA,
        session_factory: Optional[Callable] = None,
    ):
        self.name = provider_name
        self.version = provider_version
        self._path = onnx_path
        self._class_map = {int(k): int(v) for k, v in class_map.items()}
        self._input_size = int(input_size)
        self._conf = float(conf_threshold)
        self._iou = float(iou_threshold)
        self._max_det = int(max_detections)
        # Output schema selects the decode path: "phase6-infra-v1"/"tiny_v1" (raw
        # (N,6) → decode → NMS) vs "fcos_v1" (post-NMS boxes/scores/labels → adapter,
        # NO second NMS). Phase 6T-B / ADR-034.
        self._output_schema = output_schema or OUTPUT_SCHEMA
        self._session_factory = session_factory
        self._session = None
        self._input_name = ""
        self._output_name = ""
        self._output_names: list[str] = []
        self._device: Optional[ResolvedDevice] = None
        # Per-frame stage timings (ms), refreshed each detect() for observability.
        self.last_timings: dict[str, float] = {}

    # --- lifecycle ---
    def load(self, device: ResolvedDevice) -> None:
        if self._session is not None:
            return
        self._device = device
        factory = self._session_factory or self._default_session_factory
        try:
            session = factory(self._path, device.requested_ep_list)
        except Exception as exc:
            raise DetectionError("model_load_failed", f"ORT session create failed: {exc}") from exc

        inputs = session.get_inputs()
        outputs = session.get_outputs()
        if len(inputs) != 1:
            raise DetectionError("invalid_artifact", f"expected 1 model input, got {len(inputs)}")
        if len(outputs) < 1:
            raise DetectionError("invalid_artifact", "model has no outputs")
        self._session = session
        self._input_name = inputs[0].name
        self._output_name = outputs[0].name
        self._output_names = [o.name for o in outputs]

        # TRUTHFUL execution-provider reporting: whatever ORT actually bound.
        try:
            actual = session.get_providers()
            device.actual_ep = actual[0] if actual else ""
        except Exception:  # pragma: no cover - defensive
            device.actual_ep = ""
        logger.info("detector_onnx_loaded", provider=self.name,
                    requested_ep=device.requested_ep_list, actual_ep=device.actual_ep)

    @staticmethod
    def _default_session_factory(path: str, ep_list: list[str]):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        return ort.InferenceSession(path, sess_options=opts, providers=ep_list)

    def warmup(self) -> None:
        if self._session is None:
            return
        dummy = np.zeros((1, 3, self._input_size, self._input_size), dtype=np.float32)
        try:
            self._session.run([self._output_name], {self._input_name: dummy})
        except Exception as exc:  # pragma: no cover - warmup best-effort
            logger.warning("detector_warmup_failed", error=str(exc)[:120])

    def classes(self) -> list[int]:
        return sorted(set(self._class_map.values()))

    def detect(self, rgb: np.ndarray) -> DetectionResult:
        if self._session is None:
            raise DetectionError("model_load_failed", "detector not loaded")
        t0 = time.perf_counter()
        tensor, meta = letterbox(rgb, self._input_size)
        t1 = time.perf_counter()
        if self._output_schema == "fcos_v1":
            result = self._detect_fcos(tensor, meta)
            t2 = t3 = time.perf_counter()
            self.last_timings = {"preprocess_ms": (t1 - t0) * 1000.0,
                                 "inference_ms": (t2 - t1) * 1000.0, "postprocess_ms": 0.0}
            return result
        try:
            raw = self._session.run([self._output_name], {self._input_name: tensor})[0]
        except Exception as exc:
            raise DetectionError("inference_failed", f"ORT run failed: {exc}") from exc
        t2 = time.perf_counter()
        boxes, scores, class_ids = _decode_output(raw)
        result = postprocess(
            boxes_xyxy_target=boxes, scores=scores, model_class_ids=class_ids,
            meta=meta, class_map=self._class_map,
            conf_threshold=self._conf, iou_threshold=self._iou,
            max_detections=self._max_det,
            provider_name=self.name, provider_version=self.version,
            is_test_provider=False,
        )
        t3 = time.perf_counter()
        self.last_timings = {
            "preprocess_ms": (t1 - t0) * 1000.0,
            "inference_ms": (t2 - t1) * 1000.0,
            "postprocess_ms": (t3 - t2) * 1000.0,
        }
        return result

    def _detect_fcos(self, tensor: np.ndarray, meta) -> DetectionResult:
        """FCOS path: run the 3-output post-NMS model and decode via the fcos_v1
        adapter (reverse-letterbox, no second NMS). FCOS ONNX takes a [3,H,W] input."""
        from apps.processing.runtime.detector.fcos_adapter import decode_fcos_v1

        image = tensor[0] if tensor.ndim == 4 else tensor  # FCOS input is [3,H,W]
        try:
            outs = self._session.run(self._output_names, {self._input_name: image})
        except Exception as exc:
            raise DetectionError("inference_failed", f"ORT run failed: {exc}") from exc
        boxes, scores, labels = outs[0], outs[1], outs[2]
        return decode_fcos_v1(
            boxes_xyxy_target=boxes, scores=scores, labels=labels, meta=meta,
            class_map=self._class_map, conf_threshold=self._conf,
            max_detections=self._max_det, provider_name=self.name,
            provider_version=self.version,
        )

    def unload(self) -> None:
        self._session = None
        self._input_name = ""
        self._output_name = ""
        self._output_names = []

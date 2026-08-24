"""Phase 6T-B — FCOS runtime output adapter (`fcos_v1`) + OnnxDetector dispatch.

Proves the production runtime can consume the FCOS post-NMS contract
(boxes/scores/labels) → canonical Detection via reverse-letterbox, with NO second
NMS (avoids double-NMS), and that the existing (N,6) path is untouched. No torch."""
from __future__ import annotations

import math

import numpy as np

from apps.processing.runtime.detector.fcos_adapter import decode_fcos_v1
from apps.processing.runtime.detector.onnx_backend import OnnxDetector
from apps.processing.runtime.detector.preprocess import letterbox


def _meta_640_from_480x640():
    _, meta = letterbox(np.zeros((480, 640, 3), dtype=np.uint8), 640)
    return meta  # scale 1.0, pad_y 80, pad_x 0


def test_decode_fcos_reverse_letterbox_and_no_nms():
    meta = _meta_640_from_480x640()
    # two heavily-overlapping boxes, same class → BOTH must survive (FCOS already
    # NMS'd; the runtime must not NMS again).
    boxes = np.array([[100, 100, 260, 300], [104, 104, 262, 302]], dtype=float)
    scores = np.array([0.9, 0.85])
    labels = np.array([0, 0])
    res = decode_fcos_v1(
        boxes_xyxy_target=boxes, scores=scores, labels=labels, meta=meta,
        class_map={0: 0}, conf_threshold=0.25, max_detections=300,
        provider_name="fcos", provider_version="v1",
    )
    assert len(res.detections) == 2                      # no double-NMS
    d = res.detections[0]
    assert math.isclose(d.x1, 100 / 640, rel_tol=1e-6)
    assert math.isclose(d.y1, (100 - 80) / 480, rel_tol=1e-6)
    res.validate()


def test_decode_fcos_conf_filter_and_label_map():
    meta = _meta_640_from_480x640()
    boxes = np.array([[10, 90, 30, 120], [40, 90, 60, 120]], dtype=float)
    res = decode_fcos_v1(
        boxes_xyxy_target=boxes, scores=np.array([0.1, 0.9]), labels=np.array([5, 7]),
        meta=meta, class_map={5: 5}, conf_threshold=0.25, max_detections=300,
        provider_name="fcos", provider_version="v1",
    )
    # first dropped by conf; second dropped because label 7 is unmapped
    assert res.detections == []


def test_decode_fcos_empty():
    meta = _meta_640_from_480x640()
    res = decode_fcos_v1(
        boxes_xyxy_target=np.zeros((0, 4)), scores=np.zeros((0,)),
        labels=np.zeros((0,), dtype=int), meta=meta, class_map={0: 0},
        conf_threshold=0.25, max_detections=300, provider_name="fcos", provider_version="v1",
    )
    assert res.detections == []


class _FakeFcosSession:
    """Minimal ORT-like session emitting the FCOS 3-output post-NMS contract."""

    def __init__(self, boxes, scores, labels):
        self._b, self._s, self._l = boxes, scores, labels

    def get_inputs(self):
        return [type("I", (), {"name": "images"})()]

    def get_outputs(self):
        return [type("O", (), {"name": n})() for n in ("boxes", "scores", "labels")]

    def get_providers(self):
        return ["CPUExecutionProvider"]

    def run(self, names, feed):
        assert "images" in feed and feed["images"].ndim == 3  # FCOS input is [3,H,W]
        return [self._b, self._s, self._l]


def test_onnxdetector_fcos_schema_dispatch():
    from apps.processing.runtime.detector.device import DevicePolicy, resolve_device

    boxes = np.array([[100, 100, 260, 300]], dtype=np.float32)
    scores = np.array([0.8], dtype=np.float32)
    labels = np.array([0], dtype=np.int64)
    det = OnnxDetector(
        onnx_path="unused", class_map={0: 0}, provider_name="fcos-test",
        provider_version="v1", input_size=640, conf_threshold=0.25, iou_threshold=0.45,
        max_detections=300, output_schema="fcos_v1",
        session_factory=lambda path, eps: _FakeFcosSession(boxes, scores, labels),
    )
    det.load(resolve_device(DevicePolicy.CPU_ONLY, "cpu"))
    frame = (np.arange(480 * 640 * 3, dtype=np.uint8) % 255).reshape(480, 640, 3)
    res = det.detect(frame)
    res.validate()
    assert len(res.detections) == 1
    assert res.detections[0].canonical_class == "CAR"
    assert det.last_timings["inference_ms"] >= 0.0
    det.unload()

"""Phase 6 — detector runtime unit tests (framework-independent, mostly no DB).

Covers the contract, taxonomy mapping, device policy (truthful EP reporting),
letterbox + reverse-letterbox coordinate math, NMS, postprocess, the deterministic
TEST provider, and the ONNX Runtime boundary via a project-created TEST ONNX
artifact. No third-party weights, no torch, no training.
"""
from __future__ import annotations

import math
import os
import tempfile

import numpy as np
import pytest

from apps.processing.runtime.detector.contract import (
    Detection,
    DetectionError,
    DetectionResult,
)
from apps.processing.runtime.detector.device import (
    DevicePolicy,
    DeviceResolutionError,
    resolve_device,
)
from apps.processing.runtime.detector.postprocess import nms_numpy, postprocess
from apps.processing.runtime.detector.preprocess import letterbox
from apps.processing.runtime.detector.test_provider import DeterministicTestProvider


# ---------------- contract + taxonomy ----------------

def test_detection_validate_accepts_canonical():
    Detection(class_id=0, confidence=0.9, x1=0.1, y1=0.1, x2=0.5, y2=0.5).validate()


@pytest.mark.parametrize("kw", [
    {"class_id": 99, "confidence": 0.5, "x1": 0, "y1": 0, "x2": 1, "y2": 1},   # bad class
    {"class_id": 0, "confidence": 1.5, "x1": 0, "y1": 0, "x2": 1, "y2": 1},     # conf>1
    {"class_id": 0, "confidence": 0.5, "x1": -0.1, "y1": 0, "x2": 1, "y2": 1},  # oob
    {"class_id": 0, "confidence": 0.5, "x1": 0.6, "y1": 0, "x2": 0.5, "y2": 1}, # x2<x1
    {"class_id": 0, "confidence": 0.5, "x1": 0, "y1": 0, "x2": float("nan"), "y2": 1},  # NaN
    {"class_id": 0, "confidence": 0.5, "x1": 0, "y1": 0, "x2": float("inf"), "y2": 1},  # Inf
])
def test_detection_validate_rejects_bad(kw):
    with pytest.raises(DetectionError) as exc:
        Detection(**kw).validate()
    assert exc.value.code == "invalid_output"


def test_detection_to_dict_shape():
    d = Detection(class_id=5, confidence=0.5, x1=0.1, y1=0.2, x2=0.3, y2=0.4).to_dict()
    assert d["canonical_class"] == "PEDESTRIAN"
    assert d["bbox_format"] == "normalized_xyxy"
    assert d["bbox"] == [0.1, 0.2, 0.3, 0.4]


# ---------------- device policy (truthful EP) ----------------

def test_device_cpu_only_never_cuda():
    dev = resolve_device(DevicePolicy.CPU_ONLY, "cuda:0")
    assert dev.requested_ep_list == ["CPUExecutionProvider"]
    assert dev.using_gpu is False


def test_device_prefer_gpu_falls_back_to_cpu_when_no_cuda_ep():
    # The CPU onnxruntime build has no CUDA EP → honest CPU fallback, not a pretend GPU.
    dev = resolve_device(DevicePolicy.PREFER_GPU, "cuda:0")
    assert dev.gpu_device_tag == "cpu"
    assert dev.using_gpu is False
    assert "cpu fallback" in dev.note


def test_device_require_gpu_raises_without_cuda():
    with pytest.raises(DeviceResolutionError):
        resolve_device(DevicePolicy.REQUIRE_GPU, "cuda:0")


def test_device_policy_parse_default():
    assert DevicePolicy.parse(None) is DevicePolicy.PREFER_GPU
    assert DevicePolicy.parse("cpu_only") is DevicePolicy.CPU_ONLY


# ---------------- preprocess letterbox ----------------

def test_letterbox_shape_and_meta():
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    tensor, meta = letterbox(rgb, 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert 0.0 <= tensor.max() <= 1.0
    assert meta.orig_w == 640 and meta.orig_h == 480
    assert meta.scale == 1.0
    assert meta.pad_y == 80 and meta.pad_x == 0  # 640 wide fits, 480 tall padded


def test_letterbox_rejects_bad_shape():
    with pytest.raises(ValueError):
        letterbox(np.zeros((10, 10), dtype=np.uint8), 640)


# ---------------- NMS ----------------

def test_nms_suppresses_overlap():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=float)
    scores = np.array([0.9, 0.8, 0.7])
    keep = nms_numpy(boxes, scores, 0.5)
    assert keep[0] == 0 and 2 in keep and 1 not in keep


def test_nms_empty():
    assert nms_numpy(np.zeros((0, 4)), np.zeros((0,)), 0.5) == []


# ---------------- postprocess (reverse letterbox + mapping) ----------------

def _meta_640_from_480x640():
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    _, meta = letterbox(rgb, 640)
    return meta


def test_postprocess_reverse_letterbox_math():
    meta = _meta_640_from_480x640()  # scale 1.0, pad_y 80, pad_x 0
    boxes = np.array([[100, 100, 260, 300]], dtype=float)  # target px
    res = postprocess(
        boxes_xyxy_target=boxes, scores=np.array([0.9]), model_class_ids=np.array([0]),
        meta=meta, class_map={0: 0}, conf_threshold=0.25, iou_threshold=0.45,
        max_detections=100, provider_name="t", provider_version="1", is_test_provider=False,
    )
    assert len(res.detections) == 1
    d = res.detections[0]
    assert math.isclose(d.x1, 100 / 640, rel_tol=1e-6)
    assert math.isclose(d.y1, (100 - 80) / 480, rel_tol=1e-6)
    assert math.isclose(d.x2, 260 / 640, rel_tol=1e-6)
    assert math.isclose(d.y2, (300 - 80) / 480, rel_tol=1e-6)


def test_postprocess_conf_filter_and_unmapped_class():
    meta = _meta_640_from_480x640()
    boxes = np.array([[10, 10, 20, 20], [30, 30, 40, 40]], dtype=float)
    res = postprocess(
        boxes_xyxy_target=boxes, scores=np.array([0.1, 0.9]), model_class_ids=np.array([0, 7]),
        meta=meta, class_map={0: 0}, conf_threshold=0.25, iou_threshold=0.45,
        max_detections=100, provider_name="t", provider_version="1", is_test_provider=False,
    )
    # first dropped by conf; second dropped because class 7 is unmapped.
    assert res.detections == []


def test_postprocess_empty_input():
    meta = _meta_640_from_480x640()
    res = postprocess(
        boxes_xyxy_target=np.zeros((0, 4)), scores=np.zeros((0,)),
        model_class_ids=np.zeros((0,), dtype=int), meta=meta, class_map={0: 0},
        conf_threshold=0.25, iou_threshold=0.45, max_detections=100,
        provider_name="t", provider_version="1", is_test_provider=False,
    )
    assert res.detections == []


def test_postprocess_rejects_nonfinite():
    meta = _meta_640_from_480x640()
    with pytest.raises(DetectionError):
        postprocess(
            boxes_xyxy_target=np.array([[np.inf, 0, 1, 1]]), scores=np.array([0.9]),
            model_class_ids=np.array([0]), meta=meta, class_map={0: 0},
            conf_threshold=0.25, iou_threshold=0.45, max_detections=100,
            provider_name="t", provider_version="1", is_test_provider=False,
        )


# ---------------- deterministic TEST provider ----------------

def test_test_provider_is_deterministic_and_marked():
    p = DeterministicTestProvider()
    p.load()
    frame = (np.arange(480 * 640 * 3, dtype=np.uint8) % 255).reshape(480, 640, 3)
    r1 = p.detect(frame)
    r2 = p.detect(frame)
    assert r1.is_test_provider is True
    assert [d.to_dict() for d in r1.detections] == [d.to_dict() for d in r2.detections]
    r1.validate()
    assert len(r1.detections) >= 1


# ---------------- ONNX Runtime boundary (real session, project TEST artifact) ----------------

def test_onnx_backend_loads_and_detects_real_session():
    from apps.processing.runtime.detector.onnx_backend import OnnxDetector
    from apps.processing.runtime.detector.testkit import TEST_CLASS_MAP, write_test_onnx

    tmp = tempfile.mkdtemp()
    path = write_test_onnx(os.path.join(tmp, "t.onnx"), target=640)
    dev = resolve_device(DevicePolicy.PREFER_GPU, "cpu")
    det = OnnxDetector(onnx_path=path, class_map=TEST_CLASS_MAP, provider_name="onnx-test",
                       provider_version="v1", input_size=640, conf_threshold=0.25,
                       iou_threshold=0.45, max_detections=300)
    det.load(dev)
    # Truthful EP: the CPU build reports the CPU EP, never a pretend CUDA.
    assert dev.actual_ep == "CPUExecutionProvider"
    assert dev.using_gpu is False
    det.warmup()
    frame = (np.arange(480 * 640 * 3, dtype=np.uint8) % 255).reshape(480, 640, 3)
    res = det.detect(frame)
    res.validate()
    assert len(res.detections) == 2  # the const graph emits 2 boxes
    assert res.is_test_provider is False
    assert det.last_timings["inference_ms"] >= 0.0
    det.unload()


def test_onnx_backend_rejects_bad_output_shape():
    from apps.processing.runtime.detector.onnx_backend import _decode_output

    with pytest.raises(DetectionError) as exc:
        _decode_output(np.zeros((3, 5)))  # not (N,6)
    assert exc.value.code == "invalid_output"


def test_testkit_builds_valid_onnx():
    from apps.processing.runtime.detector.testkit import build_test_onnx_bytes

    data = build_test_onnx_bytes(320)
    assert data[:1] == b"\x08"  # ONNX ir_version protobuf tag (our sniff)
    assert len(data) > 0

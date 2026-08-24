"""
Detector postprocessing (Phase 6 / §23, D10). Pure NumPy.

Turns a model's decoded raw boxes (target-pixel XYXY + score + model class index)
into framework-independent `Detection`s in canonical normalized XYXY:

  validate shape/finiteness → confidence filter → map model class → canonical id
  → reverse letterbox → normalize → clamp [0,1] → per-class NMS → cap count.

Thresholds are PROVISIONAL infrastructure defaults — NOT accuracy-tuned; this
module makes no precision/recall/mAP claim. NMS and coordinate math are
deterministic and fixture-tested.
"""
from __future__ import annotations

import numpy as np

from apps.processing.runtime.detector.contract import (
    Detection,
    DetectionError,
    DetectionResult,
)
from apps.processing.runtime.detector.preprocess import LetterboxMeta
from apps.processing.taxonomy import is_valid_class_id


def nms_numpy(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Greedy IoU NMS. `boxes` = (N,4) xyxy (any consistent unit). Returns kept
    indices ordered by descending score. Deterministic."""
    if boxes.shape[0] == 0:
        return []
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        union = areas[i] + areas[rest] - inter
        iou = np.where(union > 0, inter / union, 0.0)
        order = rest[iou <= iou_threshold]
    return keep


def _reverse_letterbox(box_t: np.ndarray, meta: LetterboxMeta) -> np.ndarray:
    """Map a (…,4) xyxy box from target-pixel space back to normalized [0,1]
    original-frame space. Vectorized."""
    box = box_t.astype(np.float64).copy()
    # Undo padding + scaling → original pixel coords.
    box[..., 0] = (box[..., 0] - meta.pad_x) / meta.scale
    box[..., 2] = (box[..., 2] - meta.pad_x) / meta.scale
    box[..., 1] = (box[..., 1] - meta.pad_y) / meta.scale
    box[..., 3] = (box[..., 3] - meta.pad_y) / meta.scale
    # Normalize by original dimensions.
    box[..., 0] /= meta.orig_w
    box[..., 2] /= meta.orig_w
    box[..., 1] /= meta.orig_h
    box[..., 3] /= meta.orig_h
    return np.clip(box, 0.0, 1.0)


def postprocess(
    *,
    boxes_xyxy_target: np.ndarray,   # (N,4) float, target-pixel space
    scores: np.ndarray,              # (N,) float in [0,1]
    model_class_ids: np.ndarray,     # (N,) int, model-native class indices
    meta: LetterboxMeta,
    class_map: dict[int, int],       # model idx → canonical id
    conf_threshold: float,
    iou_threshold: float,
    max_detections: int,
    provider_name: str,
    provider_version: str,
    is_test_provider: bool,
) -> DetectionResult:
    """Full postprocess → validated `DetectionResult` (canonical normalized XYXY)."""
    boxes = np.asarray(boxes_xyxy_target, dtype=np.float64)
    scores = np.asarray(scores, dtype=np.float64)
    model_class_ids = np.asarray(model_class_ids)

    n = boxes.shape[0]
    if n == 0:
        return DetectionResult(detections=[], provider_name=provider_name,
                               provider_version=provider_version,
                               is_test_provider=is_test_provider)
    if boxes.shape != (n, 4) or scores.shape != (n,) or model_class_ids.shape != (n,):
        raise DetectionError("invalid_output", "mismatched postprocess array shapes")
    if not np.isfinite(boxes).all() or not np.isfinite(scores).all():
        raise DetectionError("invalid_output", "non-finite model output")

    # Confidence filter (before the expensive per-class NMS).
    keep_conf = scores >= conf_threshold
    if not keep_conf.any():
        return DetectionResult(detections=[], provider_name=provider_name,
                               provider_version=provider_version,
                               is_test_provider=is_test_provider)
    boxes, scores, model_class_ids = boxes[keep_conf], scores[keep_conf], model_class_ids[keep_conf]

    # Map model class → canonical; drop unmapped/invalid classes.
    canonical = np.array([class_map.get(int(c), -1) for c in model_class_ids], dtype=np.int64)
    mapped = canonical >= 0
    if not mapped.any():
        return DetectionResult(detections=[], provider_name=provider_name,
                               provider_version=provider_version,
                               is_test_provider=is_test_provider)
    boxes, scores, canonical = boxes[mapped], scores[mapped], canonical[mapped]

    # Reverse letterbox → normalized [0,1] original-frame coords.
    norm = _reverse_letterbox(boxes, meta)

    # Per-class NMS (class-aware: boxes of different classes never suppress).
    kept_idx: list[int] = []
    for cls in np.unique(canonical):
        sel = np.where(canonical == cls)[0]
        local = nms_numpy(norm[sel], scores[sel], iou_threshold)
        kept_idx.extend(int(sel[i]) for i in local)

    # Global score sort + cap (bounded payload).
    kept_idx.sort(key=lambda i: scores[i], reverse=True)
    kept_idx = kept_idx[: max(0, max_detections)]

    detections: list[Detection] = []
    for i in kept_idx:
        cls_id = int(canonical[i])
        if not is_valid_class_id(cls_id):
            continue
        x1, y1, x2, y2 = (float(norm[i, 0]), float(norm[i, 1]),
                          float(norm[i, 2]), float(norm[i, 3]))
        # Guard against degenerate ordering from numerical noise.
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        det = Detection(class_id=cls_id, confidence=float(min(1.0, max(0.0, scores[i]))),
                        x1=x1, y1=y1, x2=x2, y2=y2)
        det.validate()
        detections.append(det)

    return DetectionResult(detections=detections, provider_name=provider_name,
                           provider_version=provider_version,
                           is_test_provider=is_test_provider)

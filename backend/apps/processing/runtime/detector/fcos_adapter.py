"""
FCOS output adapter (`fcos_v1`) for the production runtime (Phase 6T-B).

torchvision FCOS bakes its postprocessing (score threshold + **NMS**) into the ONNX
graph and emits final detections `boxes[N,4] / scores[N] / labels[N]` in letterbox
target-pixel space. So the runtime must NOT run the Phase 6 raw-decode or a second
NMS (that would be double-NMS). This adapter only:

  map label→canonical → confidence filter → reverse-letterbox → clamp [0,1] → cap.

Pure NumPy (torch-free) so it lives in the production runtime. The framework-
independent canonical `Detection` contract is preserved.
"""
from __future__ import annotations

import numpy as np

from apps.processing.runtime.detector.contract import (
    Detection,
    DetectionError,
    DetectionResult,
)
from apps.processing.runtime.detector.postprocess import _reverse_letterbox
from apps.processing.runtime.detector.preprocess import LetterboxMeta
from apps.processing.taxonomy import is_valid_class_id

OUTPUT_SCHEMA = "fcos_v1"


def decode_fcos_v1(
    *,
    boxes_xyxy_target: np.ndarray,   # (N,4) final boxes, target-pixel space (post-NMS)
    scores: np.ndarray,              # (N,)
    labels: np.ndarray,              # (N,) model-native class indices
    meta: LetterboxMeta,
    class_map: dict,                 # model idx → canonical id
    conf_threshold: float,
    max_detections: int,
    provider_name: str,
    provider_version: str,
) -> DetectionResult:
    boxes = np.asarray(boxes_xyxy_target, dtype=np.float64)
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels).astype(np.int64)

    n = boxes.shape[0]
    if n == 0:
        return DetectionResult(detections=[], provider_name=provider_name,
                               provider_version=provider_version, is_test_provider=False)
    if boxes.shape != (n, 4) or scores.shape != (n,) or labels.shape != (n,):
        raise DetectionError("invalid_output", "mismatched fcos output shapes")
    if not np.isfinite(boxes).all() or not np.isfinite(scores).all():
        raise DetectionError("invalid_output", "non-finite fcos output")

    # confidence filter (FCOS already applied its own low threshold; this is the
    # runtime's configured threshold).
    keep = scores >= conf_threshold
    boxes, scores, labels = boxes[keep], scores[keep], labels[keep]
    if boxes.shape[0] == 0:
        return DetectionResult(detections=[], provider_name=provider_name,
                               provider_version=provider_version, is_test_provider=False)

    # map labels → canonical; drop unmapped
    canonical = np.array([class_map.get(int(l), -1) for l in labels], dtype=np.int64)
    mapped = canonical >= 0
    boxes, scores, canonical = boxes[mapped], scores[mapped], canonical[mapped]
    if boxes.shape[0] == 0:
        return DetectionResult(detections=[], provider_name=provider_name,
                               provider_version=provider_version, is_test_provider=False)

    # reverse letterbox → normalized [0,1]; NO NMS (FCOS already did it).
    norm = _reverse_letterbox(boxes, meta)
    order = np.argsort(scores)[::-1][: max(0, max_detections)]

    detections = []
    for i in order:
        cid = int(canonical[i])
        if not is_valid_class_id(cid):
            continue
        x1, y1, x2, y2 = float(norm[i, 0]), float(norm[i, 1]), float(norm[i, 2]), float(norm[i, 3])
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        det = Detection(class_id=cid, confidence=float(min(1.0, max(0.0, scores[i]))),
                        x1=x1, y1=y1, x2=x2, y2=y2)
        det.validate()
        detections.append(det)

    return DetectionResult(detections=detections, provider_name=provider_name,
                           provider_version=provider_version, is_test_provider=False)

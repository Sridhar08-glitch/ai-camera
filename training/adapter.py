"""
Architecture-specific raw-output adapters (Phase 6T-A / plan §41, §44).

The real model emits a raw architecture-native tensor — NOT the Phase 6 test
`(N,6)` contract. An adapter decodes that raw output into (boxes_xyxy_target,
scores, class_ids) in letterbox target-pixel space, which the EXISTING Phase 6
postprocess (class-map → reverse-letterbox → NMS) turns into canonical Detections.

Pure NumPy so the identical adapter runs on the PyTorch output and the ONNX output
during parity checks. A production model registers its adapter id (e.g. `tiny_v1`,
later `yolox_v1`) so the runtime selects the right decode.
"""
from __future__ import annotations

import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def decode_tiny_v1(raw: np.ndarray, *, input_size: int, stride: int, num_classes: int):
    """Decode TinyDetector raw output (B,S*S,5+C) → (boxes_xyxy_target, scores, class_ids).

    Single-image (B=1). Boxes are in target-pixel space (pre-reverse-letterbox)."""
    arr = np.asarray(raw, dtype=np.float64)
    if arr.ndim == 3:
        arr = arr[0]
    n_cells, ch = arr.shape
    grid = input_size // stride
    assert n_cells == grid * grid, f"expected {grid*grid} cells, got {n_cells}"
    assert ch == 5 + num_classes

    js = np.arange(n_cells) % grid           # column
    is_ = np.arange(n_cells) // grid          # row
    tx, ty, tw, th = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
    obj = _sigmoid(arr[:, 4])
    cls_logits = arr[:, 5:]
    # softmax over classes
    cls_e = np.exp(cls_logits - cls_logits.max(axis=1, keepdims=True))
    cls_p = cls_e / cls_e.sum(axis=1, keepdims=True)
    class_ids = cls_p.argmax(axis=1)
    scores = obj * cls_p.max(axis=1)

    cx = (_sigmoid(tx) + js) * stride
    cy = (_sigmoid(ty) + is_) * stride
    bw = np.clip(np.exp(np.clip(tw, -5, 5)) * stride, 1.0, input_size * 2)
    bh = np.clip(np.exp(np.clip(th, -5, 5)) * stride, 1.0, input_size * 2)
    x1 = cx - bw / 2; y1 = cy - bh / 2
    x2 = cx + bw / 2; y2 = cy + bh / 2
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    return boxes, scores, class_ids.astype(np.int64)


ADAPTERS = {"tiny_v1": decode_tiny_v1}

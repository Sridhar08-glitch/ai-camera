"""
Training preprocessing (Phase 6T-A / ADR-037). MUST match the production runtime
letterbox byte-for-byte (no train/serve skew). This is a deliberate copy of the
backend `apps.processing.runtime.detector.preprocess` bilinear algorithm — the two
live in separate environments, so they are kept in sync via a shared golden hash
(see training/tests/test_preprocess_parity.py and backend test_preprocess_bilinear.py).

Contract: letterbox to a square target, pad 114, bilinear (half-pixel centers,
align_corners=False), RGB, /255, NCHW float32. Geometry (scale/pad) is
interpolation-independent.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_PAD_VALUE = 114
INTERPOLATION = "bilinear"
PREPROCESS_CONTRACT_VERSION = "preproc-v2-bilinear"


@dataclass(frozen=True)
class LetterboxMeta:
    scale: float
    pad_x: float
    pad_y: float
    orig_w: int
    orig_h: int
    target: int


def resize_bilinear(rgb: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
    """Identical to backend resize_bilinear (ADR-037)."""
    h, w = rgb.shape[:2]
    img = rgb.astype(np.float32)
    if new_w == w and new_h == h:
        return img
    ys = (np.arange(new_h, dtype=np.float64) + 0.5) * (h / new_h) - 0.5
    xs = (np.arange(new_w, dtype=np.float64) + 0.5) * (w / new_w) - 0.5
    ys = np.clip(ys, 0.0, h - 1)
    xs = np.clip(xs, 0.0, w - 1)
    y0 = np.floor(ys).astype(np.int64); x0 = np.floor(xs).astype(np.int64)
    y1 = np.minimum(y0 + 1, h - 1); x1 = np.minimum(x0 + 1, w - 1)
    wy = (ys - y0)[:, None, None]; wx = (xs - x0)[None, :, None]
    Ia = img[y0][:, x0]; Ib = img[y0][:, x1]
    Ic = img[y1][:, x0]; Id = img[y1][:, x1]
    top = Ia * (1.0 - wx) + Ib * wx
    bot = Ic * (1.0 - wx) + Id * wx
    return top * (1.0 - wy) + bot * wy


def letterbox(rgb: np.ndarray, target: int) -> tuple[np.ndarray, LetterboxMeta]:
    """Identical to backend letterbox (ADR-037). Returns (NCHW float32 tensor, meta)."""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"expected H*W*3 rgb24, got shape {rgb.shape}")
    orig_h, orig_w = int(rgb.shape[0]), int(rgb.shape[1])
    scale = min(target / orig_w, target / orig_h)
    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))
    resized = resize_bilinear(rgb, new_w, new_h)
    canvas = np.full((target, target, 3), float(_PAD_VALUE), dtype=np.float32)
    x0, y0 = int((target - new_w) / 2.0), int((target - new_h) / 2.0)
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    tensor = np.transpose(canvas / 255.0, (2, 0, 1))[np.newaxis, ...]
    tensor = np.ascontiguousarray(tensor.astype(np.float32))
    return tensor, LetterboxMeta(scale=scale, pad_x=float(x0), pad_y=float(y0),
                                 orig_w=orig_w, orig_h=orig_h, target=target)

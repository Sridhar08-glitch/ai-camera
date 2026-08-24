"""
Aspect-ratio-preserving letterbox preprocessing (Phase 6 / §23). Pure NumPy.

Takes a canonical rgb24 frame (H×W×3 uint8) and produces a square NCHW float
tensor at the model's target size, padded to preserve aspect ratio. The
`LetterboxMeta` records the exact scale + padding so postprocess can invert the
transform back to the original frame's normalized coordinate space.

No torch. Resizing uses a deterministic NumPy **bilinear** gather (ADR-037): this
is the canonical train/serve interpolation contract — training preprocessing MUST
use the identical algorithm so there is no train/serve skew. The letterbox geometry
(scale, pad_x, pad_y) is interpolation-independent, so reverse-letterbox and all
coordinate contracts are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Grey pad value matches the common detector convention (114/255).
_PAD_VALUE = 114
# Interpolation contract version — recorded in model metadata; training must match.
INTERPOLATION = "bilinear"
PREPROCESS_CONTRACT_VERSION = "preproc-v2-bilinear"


@dataclass(frozen=True)
class LetterboxMeta:
    scale: float        # uniform scale applied to the original frame
    pad_x: float        # left padding in target pixels
    pad_y: float        # top padding in target pixels
    orig_w: int
    orig_h: int
    target: int         # square target size (e.g. 640)


def resize_bilinear(rgb: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
    """Deterministic bilinear resize (H×W×3 → float32), align_corners=False
    (half-pixel centers) — the same convention detectors train under. No external
    deps. This is the canonical resize; training preprocessing must replicate it
    byte-for-byte (ADR-037)."""
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
    """Return (tensor NCHW float32 in [0,1], LetterboxMeta) for one rgb24 frame.

    The image is scaled by a single factor so its long side == target, then centred
    on a `target×target` grey canvas. Channel order stays RGB; normalization is a
    plain /255 (PROVISIONAL — a model-specific mean/std belongs to Phase 6T config).
    """
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"expected H*W*3 rgb24, got shape {rgb.shape}")
    orig_h, orig_w = int(rgb.shape[0]), int(rgb.shape[1])
    if orig_h == 0 or orig_w == 0:
        raise ValueError("empty frame")

    scale = min(target / orig_w, target / orig_h)
    new_w = max(1, int(round(orig_w * scale)))
    new_h = max(1, int(round(orig_h * scale)))
    resized = resize_bilinear(rgb, new_w, new_h)  # float32 HWC

    canvas = np.full((target, target, 3), float(_PAD_VALUE), dtype=np.float32)
    pad_x = (target - new_w) / 2.0
    pad_y = (target - new_h) / 2.0
    x0, y0 = int(pad_x), int(pad_y)
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized

    # HWC float32 → NCHW float32 in [0,1].
    tensor = canvas / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]
    tensor = np.ascontiguousarray(tensor)

    meta = LetterboxMeta(scale=scale, pad_x=float(x0), pad_y=float(y0),
                         orig_w=orig_w, orig_h=orig_h, target=target)
    return tensor, meta

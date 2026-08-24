"""Phase 6T-A — bilinear letterbox preprocessing contract (ADR-037).

Locks the train/serve interpolation contract with a golden hash so any drift (or a
future accidental revert to nearest-neighbour) is caught. The identical algorithm +
golden value are mirrored in the training package's parity test.
"""
from __future__ import annotations

import hashlib

import numpy as np

from apps.processing.runtime.detector.preprocess import (
    INTERPOLATION,
    PREPROCESS_CONTRACT_VERSION,
    letterbox,
    resize_bilinear,
)


def _fixed_frame():
    # Deterministic gradient frame (H=48, W=64).
    return (np.arange(48 * 64 * 3, dtype=np.uint8) % 251).reshape(48, 64, 3)


def test_contract_identifiers():
    assert INTERPOLATION == "bilinear"
    assert PREPROCESS_CONTRACT_VERSION == "preproc-v2-bilinear"


def test_letterbox_geometry_unchanged():
    # Geometry (scale/pad/shape) is interpolation-independent — reverse-letterbox safe.
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    tensor, meta = letterbox(rgb, 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert meta.scale == 1.0 and meta.pad_y == 80 and meta.pad_x == 0
    assert 0.0 <= float(tensor.max()) <= 1.0


def test_bilinear_resize_known_values():
    # Upsample a 2x2 to 4x4; center-ish samples interpolate (not just nearest copies).
    img = np.array([[[0, 0, 0], [90, 90, 90]],
                    [[90, 90, 90], [0, 0, 0]]], dtype=np.uint8)
    out = resize_bilinear(img, 4, 4)
    assert out.shape == (4, 4, 3)
    # bilinear must produce intermediate values not present in the 2-value input
    vals = set(np.round(out[:, :, 0].ravel(), 3))
    assert vals - {0.0, 90.0}  # at least one interpolated value


def test_letterbox_golden_hash_locks_contract():
    # GOLDEN: any change to the bilinear letterbox output changes this hash.
    tensor, _ = letterbox(_fixed_frame(), 128)
    digest = hashlib.sha256(np.ascontiguousarray(tensor).tobytes()).hexdigest()
    # Recorded golden for the bilinear contract (preproc-v2-bilinear).
    assert digest == GOLDEN_LETTERBOX_SHA256, (
        f"preprocessing output changed — got {digest}. If this is an intentional, "
        f"approved contract change, update GOLDEN_LETTERBOX_SHA256 and model metadata."
    )


# Computed once for the bilinear contract on _fixed_frame() @ target=128.
GOLDEN_LETTERBOX_SHA256 = "2f72c602aa15a69cfe501d7455edfef23f766b6b84bb6a137d4fe81607fcad48"

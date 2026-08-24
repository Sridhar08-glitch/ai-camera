"""
Project-created synthetic SMOKE dataset (Phase 6T-A). TEST_ONLY — NOT real data.

Draws simple geometric rectangles ("objects") of canonical classes onto blank
frames and returns deterministic (image, boxes) pairs. Contains **no third-party
dataset content**. Its only purpose is to exercise the training→checkpoint→
resume→eval→export→parity plumbing. It is never a real traffic dataset and any
model trained on it is TEST_ONLY and must never be activated.
"""
from __future__ import annotations

import numpy as np

# training/ must NOT import the Django backend (ADR-033). The canonical taxonomy v1
# has 6 classes {CAR,BUS,TRUCK,MOTORCYCLE,BICYCLE,PEDESTRIAN}; fixed here by contract.
NUM_CLASSES = 6


def _draw_box(img, x1, y1, x2, y2, color):
    img[y1:y2, x1:x2] = color


def make_sample(seed: int, w: int = 96, h: int = 96, max_objs: int = 3):
    """Deterministic (image HxWx3 uint8, boxes [(cls,x1,y1,x2,y2)]) for a seed."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 20, dtype=np.uint8)
    n = int(rng.integers(1, max_objs + 1))
    boxes = []
    for _ in range(n):
        cls = int(rng.integers(0, NUM_CLASSES))
        bw = int(rng.integers(w // 8, w // 3))
        bh = int(rng.integers(h // 8, h // 3))
        x1 = int(rng.integers(0, w - bw)); y1 = int(rng.integers(0, h - bh))
        x2, y2 = x1 + bw, y1 + bh
        color = np.array([(cls * 37) % 256, (cls * 91) % 256, 200], dtype=np.uint8)
        _draw_box(img, x1, y1, x2, y2, color)
        boxes.append((cls, x1, y1, x2, y2))
    return img, boxes


def make_dataset(n: int, *, base_seed: int = 0, w: int = 96, h: int = 96):
    """A deterministic list of samples. group_key ties samples to a 'sequence' so the
    leakage-safe splitter has something to group on."""
    out = []
    for i in range(n):
        img, boxes = make_sample(base_seed + i, w=w, h=h)
        out.append({"image": img, "boxes": boxes, "group_key": f"seq{i // 4}",
                    "sample_id": f"syn_{base_seed}_{i}"})
    return out

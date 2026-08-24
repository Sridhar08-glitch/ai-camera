"""
Deterministic TEST detector provider (Phase 6 / §guardrails). NOT REAL AI.

`DeterministicTestProvider` emits fixed, reproducible boxes derived purely from a
frame's pixel content — no model, no learning, no inference. It exists so the whole
pipeline (persistence, API, frontend, retention) can be exercised end-to-end on real
video WITHOUT any third-party pretrained weights. Its output is meaningless as
detection and must always be surfaced as TEST (`is_test_provider=True`). It can
never be registered or activated as a production model.
"""
from __future__ import annotations

import numpy as np

from apps.processing.runtime.detector.contract import Detection, DetectionResult
from apps.processing.taxonomy import CANONICAL_CLASSES

PROVIDER_NAME = "test"
PROVIDER_VERSION = "deterministic-v1"


class DeterministicTestProvider:
    """Reproducible pseudo-detections from frame content. Explicitly NOT real AI."""

    name = PROVIDER_NAME
    version = PROVIDER_VERSION
    is_test_provider = True

    def __init__(self, *, max_boxes: int = 3):
        self._max_boxes = max(1, max_boxes)
        self._loaded = False

    # --- DetectorProvider lifecycle (no model to load) ---
    def load(self, device=None) -> None:  # device accepted for protocol symmetry
        self._loaded = True

    def warmup(self) -> None:
        return None

    def classes(self) -> list[int]:
        return list(CANONICAL_CLASSES.keys())

    def unload(self) -> None:
        self._loaded = False

    # --- deterministic pseudo-detection ---
    def _seed(self, rgb: np.ndarray) -> int:
        # Stable content-derived seed: cheap strided checksum + shape. Deterministic.
        h, w = rgb.shape[0], rgb.shape[1]
        s = int(rgb[:: max(1, h // 16), :: max(1, w // 16), :].sum())
        return (s * 2654435761 + h * 40503 + w) & 0x7FFFFFFF

    def detect(self, rgb: np.ndarray) -> DetectionResult:
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError(f"expected H*W*3 rgb24, got {rgb.shape}")
        rng = np.random.default_rng(self._seed(rgb))
        n = int(rng.integers(1, self._max_boxes + 1))
        class_ids = list(CANONICAL_CLASSES.keys())

        detections: list[Detection] = []
        for k in range(n):
            # Deterministic box in normalized coords; guaranteed x1<x2, y1<y2.
            cx, cy = float(rng.uniform(0.2, 0.8)), float(rng.uniform(0.2, 0.8))
            bw, bh = float(rng.uniform(0.05, 0.25)), float(rng.uniform(0.05, 0.25))
            x1 = max(0.0, cx - bw / 2); x2 = min(1.0, cx + bw / 2)
            y1 = max(0.0, cy - bh / 2); y2 = min(1.0, cy + bh / 2)
            cls_id = class_ids[(self._seed(rgb) + k) % len(class_ids)]
            conf = round(0.30 + 0.60 * float(rng.random()), 4)  # bounded [0.30,0.90]
            det = Detection(class_id=cls_id, confidence=conf, x1=x1, y1=y1, x2=x2, y2=y2)
            det.validate()
            detections.append(det)

        return DetectionResult(
            detections=detections,
            provider_name=self.name,
            provider_version=self.version,
            is_test_provider=True,
        )

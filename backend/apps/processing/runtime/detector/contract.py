"""
Framework-independent detection contract (Phase 6 / §23, D10).

A `Detection` never exposes ONNX/PyTorch tensors or framework classes. The
canonical bounding-box representation is **normalized XYXY in [0,1]** (resolution-
independent, letterbox-inverted), so results survive resolution changes and map
directly onto image-normalized ROIs/lines.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.processing.taxonomy import canonical_name, is_valid_class_id


class DetectionError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


@dataclass
class Detection:
    class_id: int                 # canonical taxonomy id
    confidence: float             # [0,1]
    # Canonical box: normalized XYXY in [0,1], x1<=x2, y1<=y2.
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def canonical_class(self) -> str:
        return canonical_name(self.class_id)

    def validate(self) -> None:
        if not is_valid_class_id(self.class_id):
            raise DetectionError("invalid_output", f"unknown class_id {self.class_id}")
        if not (0.0 <= self.confidence <= 1.0):
            raise DetectionError("invalid_output", f"confidence out of range {self.confidence}")
        for name, v in (("x1", self.x1), ("y1", self.y1), ("x2", self.x2), ("y2", self.y2)):
            if v != v or v in (float("inf"), float("-inf")):  # NaN/Inf
                raise DetectionError("invalid_output", f"non-finite {name}")
            if not (0.0 <= v <= 1.0):
                raise DetectionError("invalid_output", f"{name} out of [0,1]: {v}")
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise DetectionError("invalid_output", "x2<x1 or y2<y1")

    def to_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "canonical_class": self.canonical_class,
            "confidence": round(float(self.confidence), 6),
            "bbox": [round(float(self.x1), 6), round(float(self.y1), 6),
                     round(float(self.x2), 6), round(float(self.y2), 6)],
            "bbox_format": "normalized_xyxy",
        }


@dataclass
class DetectionResult:
    """A frame's detections + the provider/model identity that produced them."""

    detections: list[Detection] = field(default_factory=list)
    provider_name: str = ""
    provider_version: str = ""
    is_test_provider: bool = False   # deterministic test output — NOT real AI

    def validate(self) -> None:
        for d in self.detections:
            d.validate()

    def to_payload(self) -> list[dict]:
        return [d.to_dict() for d in self.detections]

"""
Canonical traffic-object taxonomy (Phase 6 / D8, frozen §19). Versioned.

All detector outputs map into this stable taxonomy so model swaps do not change
analytics semantics. PEDESTRIAN is bounding-box only — no recognition/identification
(frozen §32). Class mappings from source datasets are versioned in Phase 6T.
"""
from __future__ import annotations

TAXONOMY_VERSION = "v1"

# Canonical id → canonical class name. Order is stable and part of the contract.
CANONICAL_CLASSES: dict[int, str] = {
    0: "CAR",
    1: "BUS",
    2: "TRUCK",
    3: "MOTORCYCLE",
    4: "BICYCLE",
    5: "PEDESTRIAN",
}

CANONICAL_NAME_TO_ID: dict[str, int] = {v: k for k, v in CANONICAL_CLASSES.items()}


def is_valid_class_id(class_id: int) -> bool:
    return class_id in CANONICAL_CLASSES


def canonical_name(class_id: int) -> str:
    return CANONICAL_CLASSES.get(class_id, "")

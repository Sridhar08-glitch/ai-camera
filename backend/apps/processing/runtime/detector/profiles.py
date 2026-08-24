"""
PROVISIONAL detector runtime profiles (Phase 6 / task #15).

Three coarse operating points — Quality / Balanced / Performance (Q/B/P) — that bundle
the *runtime* knobs a detector session can trade off: input letterbox size, confidence
and IoU thresholds, and device policy. These are INFRASTRUCTURE defaults only.

They are NOT accuracy-tuned and carry NO precision/recall/mAP guarantee — real
operating points come from Phase 6T evaluation against a governed model + dataset.
Nothing here trains, downloads, or bundles weights.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectorProfile:
    key: str
    input_size: int
    conf: float
    iou: float
    device_policy: str
    note: str


# PROVISIONAL — subject to change once Phase 6T evaluation exists.
PROFILES: dict[str, DetectorProfile] = {
    "quality": DetectorProfile(
        key="quality", input_size=960, conf=0.20, iou=0.50, device_policy="PREFER_GPU",
        note="PROVISIONAL: larger input, lower conf — more candidate boxes, slower.",
    ),
    "balanced": DetectorProfile(
        key="balanced", input_size=640, conf=0.25, iou=0.45, device_policy="PREFER_GPU",
        note="PROVISIONAL: default operating point.",
    ),
    "performance": DetectorProfile(
        key="performance", input_size=416, conf=0.35, iou=0.45, device_policy="PREFER_GPU",
        note="PROVISIONAL: smaller input, higher conf — fewer boxes, faster.",
    ),
}

DEFAULT_PROFILE = "balanced"


def get_profile(key: str | None) -> DetectorProfile:
    return PROFILES.get((key or DEFAULT_PROFILE).lower(), PROFILES[DEFAULT_PROFILE])

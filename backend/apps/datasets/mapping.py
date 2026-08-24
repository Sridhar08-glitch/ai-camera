"""
Versioned source-label → canonical-taxonomy class mapping (Phase 6T-A / plan §25).

Ambiguous source labels are NEVER silently mapped. Each mapping version is explicit:
known labels map to a canonical id; labels in `drop` are intentionally excluded
(logged); anything else is "unknown" and reported, never guessed. Every
DatasetVersion records which mapping version it used.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.processing.taxonomy import CANONICAL_NAME_TO_ID, is_valid_class_id


@dataclass(frozen=True)
class ClassMapping:
    version: str
    # normalized source label (lower-case, stripped) → canonical id
    label_to_canonical: dict
    drop: frozenset = field(default_factory=frozenset)  # intentionally-excluded labels

    def map_label(self, source_label: str):
        """Return (canonical_id or None, status) where status ∈
        {mapped, dropped, unknown}. Never guesses an ambiguous label."""
        key = (source_label or "").strip().lower()
        if key in self.drop:
            return None, "dropped"
        if key in self.label_to_canonical:
            cid = self.label_to_canonical[key]
            if not is_valid_class_id(cid):
                return None, "unknown"
            return cid, "mapped"
        return None, "unknown"


# Mapping v1: common vehicle/pedestrian source labels → canonical taxonomy v1.
# Only unambiguous synonyms are included. Ambiguous terms (e.g. "vehicle", "rider")
# are deliberately NOT mapped — they surface as unknown for human review.
_C = CANONICAL_NAME_TO_ID
MAPPING_V1 = ClassMapping(
    version="map-v1",
    label_to_canonical={
        "car": _C["CAR"], "automobile": _C["CAR"], "sedan": _C["CAR"], "passenger car": _C["CAR"],
        "bus": _C["BUS"], "coach": _C["BUS"],
        "truck": _C["TRUCK"], "lorry": _C["TRUCK"], "pickup truck": _C["TRUCK"],
        "motorcycle": _C["MOTORCYCLE"], "motorbike": _C["MOTORCYCLE"], "motor": _C["MOTORCYCLE"],
        "bicycle": _C["BICYCLE"], "bike": _C["BICYCLE"], "cycle": _C["BICYCLE"],
        "pedestrian": _C["PEDESTRIAN"], "person": _C["PEDESTRIAN"], "people": _C["PEDESTRIAN"],
    },
    drop=frozenset({"dontcare", "ignore", "misc"}),
)

# UVH-26 / BMD-45 (AIM@IISc) mapping. Source class NAMES verified from the actual
# downloaded COCO annotation `categories` (2026-07-16): Hatchback, Sedan, SUV, MUV,
# Bus, Truck, Three-wheeler, Two-wheeler, LCV, Mini-bus, Tempo-traveller, Bicycle,
# Van, Others. Ambiguous / no-canonical-equivalent classes are EXCLUDED (dropped),
# never force-mapped (Three-wheeler/auto-rickshaw has no canonical class; LCV/Van/
# Tempo-traveller are ambiguous between CAR/TRUCK/BUS; Others is misc).
UVH_BMD_5CLASS_V1 = ClassMapping(
    version="uvh_bmd_5class_v1",
    label_to_canonical={
        "hatchback": _C["CAR"], "sedan": _C["CAR"], "suv": _C["CAR"], "muv": _C["CAR"],
        "bus": _C["BUS"], "mini-bus": _C["BUS"], "minibus": _C["BUS"],
        "truck": _C["TRUCK"],
        "two-wheeler": _C["MOTORCYCLE"], "twowheeler": _C["MOTORCYCLE"], "2-wheeler": _C["MOTORCYCLE"],
        "bicycle": _C["BICYCLE"],
    },
    drop=frozenset({"three-wheeler", "3-wheeler", "auto-rickshaw", "lcv",
                    "tempo-traveller", "tempo traveller", "van", "others", "other"}),
)

_REGISTRY = {MAPPING_V1.version: MAPPING_V1, UVH_BMD_5CLASS_V1.version: UVH_BMD_5CLASS_V1}


def get_mapping(version: str) -> ClassMapping:
    if version not in _REGISTRY:
        raise KeyError(f"unknown class-mapping version '{version}'")
    return _REGISTRY[version]

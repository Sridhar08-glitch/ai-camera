"""Phase 6T-B — uvh_bmd_5class_v1 mapping verified against the REAL UVH-26/BMD-45
14-class taxonomy (downloaded COCO categories, 2026-07-16). No torch."""
from __future__ import annotations

from apps.datasets.mapping import get_mapping
from apps.processing.taxonomy import CANONICAL_NAME_TO_ID as C

MAP = get_mapping("uvh_bmd_5class_v1")

# The exact real source categories from the downloaded UVH-26 annotation JSON.
REAL_CLASSES = ["Hatchback", "Sedan", "SUV", "MUV", "Bus", "Truck", "Three-wheeler",
                "Two-wheeler", "LCV", "Mini-bus", "Tempo-traveller", "Bicycle", "Van", "Others"]


VEHICLE_5 = {C["CAR"], C["BUS"], C["TRUCK"], C["MOTORCYCLE"], C["BICYCLE"]}


def test_clean_mappings_cover_all_five_vehicle_classes():
    got = {}
    for label in REAL_CLASSES:
        cid, status = MAP.map_label(label)
        if status == "mapped":
            got.setdefault(cid, []).append(label)
    # exactly the 5 vehicle classes are produced (PEDESTRIAN is NOT in these
    # vehicle-only datasets — the V1 model is 5-class; see report class-coverage gate)
    assert set(got.keys()) == VEHICLE_5
    assert C["PEDESTRIAN"] not in got
    assert set(got[C["CAR"]]) == {"Hatchback", "Sedan", "SUV", "MUV"}
    assert set(got[C["BUS"]]) == {"Bus", "Mini-bus"}
    assert got[C["TRUCK"]] == ["Truck"]
    assert got[C["MOTORCYCLE"]] == ["Two-wheeler"]
    assert got[C["BICYCLE"]] == ["Bicycle"]


def test_ambiguous_classes_excluded_not_forcemapped():
    for label in ["Three-wheeler", "LCV", "Tempo-traveller", "Van", "Others"]:
        cid, status = MAP.map_label(label)
        assert cid is None
        assert status == "dropped"  # explicitly excluded, never guessed

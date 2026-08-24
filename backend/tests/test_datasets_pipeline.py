"""Phase 6T-A — COCO conversion, validation, dedup, leakage-safe splitting (no torch)."""
from __future__ import annotations

import pytest

from apps.datasets.coco import canonical_categories, to_canonical_coco
from apps.datasets.dedup import dedup_report, find_exact_duplicates
from apps.datasets.mapping import MAPPING_V1, get_mapping
from apps.datasets.manifests import SampleRecord
from apps.datasets.splits import (
    assign_splits,
    check_no_leakage,
    split_counts,
)
from apps.datasets.validation import validate_coco
from apps.processing.taxonomy import CANONICAL_NAME_TO_ID


# ---- class mapping ----

def test_mapping_maps_synonyms():
    assert MAPPING_V1.map_label("automobile") == (CANONICAL_NAME_TO_ID["CAR"], "mapped")
    assert MAPPING_V1.map_label("motorbike") == (CANONICAL_NAME_TO_ID["MOTORCYCLE"], "mapped")


def test_mapping_drops_and_unknowns_not_guessed():
    assert MAPPING_V1.map_label("dontcare")[1] == "dropped"
    # ambiguous label must NOT be silently mapped
    cid, status = MAPPING_V1.map_label("vehicle")
    assert cid is None and status == "unknown"


def test_get_mapping_unknown_version():
    with pytest.raises(KeyError):
        get_mapping("nope")


# ---- COCO conversion ----

def test_coco_conversion_maps_and_drops():
    images = [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}]
    raw = [
        {"image_id": 1, "source_label": "car", "bbox": [10, 10, 20, 20]},
        {"image_id": 1, "source_label": "vehicle", "bbox": [0, 0, 5, 5]},  # unknown → dropped
        {"image_id": 1, "source_label": "dontcare", "bbox": [1, 1, 2, 2]}, # dropped
    ]
    doc, report = to_canonical_coco(
        images=images, raw_annotations=raw, mapping_version="map-v1",
        source_format="test", timestamp="2026-07-16T00:00:00Z",
    )
    assert len(doc["annotations"]) == 1  # only the car mapped
    assert doc["annotations"][0]["category_id"] == CANONICAL_NAME_TO_ID["CAR"]
    assert report["counts"]["mapped"] == 1
    assert report["counts"]["dropped"] == 1
    assert report["counts"]["unknown"] == 1
    assert report["unknown_labels"].get("vehicle") == 1
    assert doc["info"]["taxonomy_version"] == "v1"
    assert {c["id"] for c in canonical_categories()} == set(CANONICAL_NAME_TO_ID.values())


# ---- validation ----

def test_validation_flags_bad_boxes():
    doc = {
        "images": [{"id": 1, "file_name": "a.jpg", "width": 100, "height": 100}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 0, "bbox": [10, 10, 20, 20]},   # ok
            {"id": 2, "image_id": 1, "category_id": 0, "bbox": [90, 90, 50, 50]},   # oob
            {"id": 3, "image_id": 1, "category_id": 0, "bbox": [0, 0, 0, 10]},      # zero-area
            {"id": 4, "image_id": 1, "category_id": 99, "bbox": [1, 1, 2, 2]},      # unknown cat
            {"id": 5, "image_id": 1, "category_id": 0, "bbox": [10, 10, 20, 20]},   # duplicate
        ],
        "categories": canonical_categories(),
    }
    rep = validate_coco(doc)
    assert rep["issues"]["out_of_bounds"] >= 1
    assert rep["issues"]["zero_area"] >= 1
    assert rep["issues"]["unknown_category"] == 1
    assert rep["issues"]["duplicate_annotation"] >= 1
    assert rep["ok"] is False  # unknown category present


def test_validation_empty_and_balance():
    doc = {
        "images": [{"id": 1, "width": 10, "height": 10}, {"id": 2, "width": 10, "height": 10}],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 0, "bbox": [1, 1, 2, 2]}],
        "categories": canonical_categories(),
    }
    rep = validate_coco(doc)
    assert rep["empty_image_count"] == 1  # image 2 has no annotations


# ---- dedup ----

def test_exact_duplicates_found():
    items = [("a", "h1"), ("b", "h1"), ("c", "h2")]
    dupes = find_exact_duplicates(items)
    assert "h1" in dupes and set(dupes["h1"]) == {"a", "b"}
    rep = dedup_report(items)
    assert rep["duplicate_groups"] == 1
    assert rep["duplicate_sample_ids"] == ["b"]


# ---- leakage-safe splitting ----

def _grouped_records(n_groups=10, per_group=5):
    recs = []
    for g in range(n_groups):
        for i in range(per_group):
            sid = f"g{g}_s{i}"
            recs.append(SampleRecord(sample_id=sid, media_checksum=f"c{g}_{i}",
                                     group_key=f"video{g}", class_ids=[0]))
    return recs


def test_split_is_leakage_free_by_group():
    recs = _grouped_records()
    out = assign_splits(recs, seed=42, ratios=(0.6, 0.2, 0.2))
    assert check_no_leakage(out) == []  # no group crosses splits
    counts = split_counts(out)
    assert sum(counts.values()) == len(recs)
    assert counts["train"] > 0 and counts["val"] > 0 and counts["test"] > 0


def test_split_deterministic_same_seed():
    recs = _grouped_records()
    a = assign_splits(recs, seed=7)
    b = assign_splits(recs, seed=7)
    assert [(r.sample_id, r.split) for r in a] == [(r.sample_id, r.split) for r in b]


def test_split_different_seed_can_differ():
    recs = _grouped_records(n_groups=20)
    a = {r.sample_id: r.split for r in assign_splits(recs, seed=1)}
    b = {r.sample_id: r.split for r in assign_splits(recs, seed=2)}
    assert a != b  # extremely likely with 20 groups


def test_exact_duplicate_media_cannot_cross_splits():
    # Two samples in DIFFERENT group_keys but SAME media checksum must not leak.
    recs = [
        SampleRecord(sample_id="x", media_checksum="DUP", group_key="videoA"),
        SampleRecord(sample_id="y", media_checksum="DUP", group_key="videoB"),
    ]
    # add filler groups so splits are non-trivial
    recs += _grouped_records(n_groups=8)
    out = assign_splits(recs, seed=3)
    by_id = {r.sample_id: r.split for r in out}
    assert by_id["x"] == by_id["y"]  # forced into the same split via checksum union
    assert check_no_leakage(out) == []

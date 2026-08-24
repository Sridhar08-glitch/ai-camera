"""
Canonical COCO-JSON conversion (Phase 6T-A / plan §22, D8).

The canonical training annotation format is COCO JSON. Source annotations remain
immutable; this module builds a *derived* canonical COCO document whose category
ids are the project canonical taxonomy and records conversion provenance (source
format, mapping version, converter version, timestamp).

Framework-independent (pure Python); the training package reads the derived COCO
files directly.
"""
from __future__ import annotations

from apps.datasets.mapping import get_mapping
from apps.processing.taxonomy import CANONICAL_CLASSES, TAXONOMY_VERSION

CONVERTER_VERSION = "coco-conv-v1"


def canonical_categories() -> list[dict]:
    """COCO `categories` = canonical taxonomy (id + name), stable order."""
    return [{"id": cid, "name": name, "supercategory": "traffic"}
            for cid, name in sorted(CANONICAL_CLASSES.items())]


def to_canonical_coco(
    *,
    images: list[dict],           # [{id, file_name, width, height, group_key?, checksum?}]
    raw_annotations: list[dict],  # [{image_id, source_label, bbox:[x,y,w,h]}]
    mapping_version: str,
    source_format: str,
    timestamp: str,               # caller supplies (deterministic; no wall-clock here)
) -> tuple[dict, dict]:
    """Build (coco_document, conversion_report).

    Boxes are COCO xywh in pixels. Unmapped/ambiguous labels are dropped and counted
    in the report — never silently mapped. Returns the canonical COCO dict + a report.
    """
    mapping = get_mapping(mapping_version)
    coco_annotations: list[dict] = []
    counts = {"mapped": 0, "dropped": 0, "unknown": 0}
    unknown_labels: dict[str, int] = {}
    next_id = 1

    for ann in raw_annotations:
        cid, status = mapping.map_label(ann.get("source_label", ""))
        counts[status] = counts.get(status, 0) + 1
        if status != "mapped":
            if status == "unknown":
                lbl = (ann.get("source_label") or "").strip().lower()
                unknown_labels[lbl] = unknown_labels.get(lbl, 0) + 1
            continue
        bbox = ann.get("bbox") or [0, 0, 0, 0]
        x, y, w, h = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        coco_annotations.append({
            "id": next_id,
            "image_id": ann["image_id"],
            "category_id": cid,
            "bbox": [x, y, w, h],
            "area": max(0.0, w) * max(0.0, h),
            "iscrowd": 0,
        })
        next_id += 1

    document = {
        "info": {
            "description": "canonical-taxonomy detection dataset",
            "taxonomy_version": TAXONOMY_VERSION,
            "class_mapping_version": mapping_version,
            "converter_version": CONVERTER_VERSION,
            "source_format": source_format,
            "converted_at": timestamp,
        },
        "images": images,
        "annotations": coco_annotations,
        "categories": canonical_categories(),
    }
    report = {
        "counts": counts,
        "unknown_labels": unknown_labels,
        "image_count": len(images),
        "annotation_count": len(coco_annotations),
    }
    return document, report

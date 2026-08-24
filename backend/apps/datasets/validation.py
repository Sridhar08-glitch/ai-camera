"""
Dataset validation report (Phase 6T-A / plan §24). Pure Python, no image decode
required for the structural checks (a decode hook is provided but optional so the
validator runs in the torch-free backend env). Produces a bounded JSON report used
as a training-eligibility precondition.
"""
from __future__ import annotations

from collections import Counter

from apps.processing.taxonomy import is_valid_class_id


def validate_coco(document: dict, *, tiny_area_frac: float = 0.001) -> dict:
    """Structural validation of a canonical COCO document. Returns a report dict.

    Checks: invalid/out-of-bounds/zero-area boxes, unknown categories, duplicate
    annotations, empty images, class imbalance, tiny-object share, resolution
    distribution. Does not decode pixels (that is an optional separate step)."""
    images = {img["id"]: img for img in document.get("images", [])}
    anns = document.get("annotations", [])
    valid_cat = {c["id"] for c in document.get("categories", [])}

    issues = {
        "invalid_bbox": 0, "out_of_bounds": 0, "zero_area": 0,
        "unknown_category": 0, "duplicate_annotation": 0, "tiny_objects": 0,
    }
    per_class = Counter()
    seen = set()
    images_with_anns = set()
    resolutions = Counter()

    for img in document.get("images", []):
        w, h = int(img.get("width", 0) or 0), int(img.get("height", 0) or 0)
        resolutions[f"{w}x{h}"] += 1

    for a in anns:
        cid = a.get("category_id")
        img = images.get(a.get("image_id"))
        bbox = a.get("bbox") or []
        if cid not in valid_cat or not is_valid_class_id(cid):
            issues["unknown_category"] += 1
        else:
            per_class[cid] += 1
        images_with_anns.add(a.get("image_id"))

        if len(bbox) != 4:
            issues["invalid_bbox"] += 1
            continue
        x, y, bw, bh = bbox
        if bw <= 0 or bh <= 0:
            issues["zero_area"] += 1
        if img is not None:
            W, H = float(img.get("width", 0) or 0), float(img.get("height", 0) or 0)
            if W > 0 and H > 0:
                if x < 0 or y < 0 or (x + bw) > W + 1e-6 or (y + bh) > H + 1e-6:
                    issues["out_of_bounds"] += 1
                if (bw * bh) < tiny_area_frac * (W * H):
                    issues["tiny_objects"] += 1
        key = (a.get("image_id"), cid, round(float(x), 2), round(float(y), 2),
               round(float(bw), 2), round(float(bh), 2))
        if key in seen:
            issues["duplicate_annotation"] += 1
        seen.add(key)

    empty_images = [iid for iid in images if iid not in images_with_anns]
    total = sum(per_class.values()) or 1
    class_balance = {str(cid): round(per_class[cid] / total, 4) for cid in per_class}

    return {
        "issues": issues,
        "image_count": len(images),
        "annotation_count": len(anns),
        "empty_image_count": len(empty_images),
        "per_class_counts": {str(k): v for k, v in per_class.items()},
        "class_balance": class_balance,
        "resolution_distribution": dict(resolutions),
        "ok": all(v == 0 for k, v in issues.items()
                  if k in ("invalid_bbox", "unknown_category")),
    }

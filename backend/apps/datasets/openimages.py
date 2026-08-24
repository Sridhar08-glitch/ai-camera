"""
Open Images metadata-ONLY candidate selection (Phase 6T-B / plan Part M).

Operates purely on Open Images **metadata** (image-info rows + box rows) — it does
NOT download image pixels. It selects vehicle-class images that carry sufficient
per-image rights metadata and a commercially-permissive license, and produces a
**candidate evidence manifest**. Every candidate is marked **pending human/legal
approval** and is NEVER made production-eligible automatically (Google disclaims
per-image license accuracy — a human/legal spot-check is mandatory, plan §5.3/Part Q).

Input row shapes (subset of official Open Images CSV columns):
  image_meta: {image_id, license, author, original_url, original_landing_url, title}
  box_rows:   {image_id, label}   (label = human-readable class name)
"""
from __future__ import annotations

from collections import defaultdict

# Open Images vehicle class names → canonical taxonomy (via mapping-v1 synonyms).
VEHICLE_CLASSES = {"Car", "Bus", "Truck", "Motorcycle", "Bicycle"}

# Commercially-permissive license substrings (CC BY / CC0 / public domain). NC/ND
# are excluded; SA is excluded here to avoid copyleft ambiguity for a first model.
PERMISSIVE_LICENSE_MARKERS = (
    "creativecommons.org/licenses/by/",
    "creativecommons.org/publicdomain/zero/",
    "creativecommons.org/publicdomain/mark/",
)
_EXCLUDE_MARKERS = ("/by-nc", "/by-nd", "/by-sa", "-nc", "-nd", "-sa")


def _is_permissive(license_url: str) -> bool:
    u = (license_url or "").lower()
    if not u:
        return False
    if any(m in u for m in _EXCLUDE_MARKERS):
        return False
    return any(m in u for m in PERMISSIVE_LICENSE_MARKERS)


def select_candidates(image_meta: list, box_rows: list, *, min_boxes: int = 1) -> dict:
    """Metadata-only candidate selection. Returns candidates + per-class counts +
    exclusion reasons. No pixels are read. Nothing is approved."""
    # index boxes by image, keep only vehicle classes
    boxes_by_image = defaultdict(list)
    for b in box_rows:
        if b.get("label") in VEHICLE_CLASSES:
            boxes_by_image[b["image_id"]].append(b["label"])

    candidates = []
    excluded = {"no_vehicle_boxes": 0, "missing_license": 0, "non_permissive_license": 0,
                "missing_rights_metadata": 0}
    class_counts = {c: 0 for c in VEHICLE_CLASSES}

    for img in image_meta:
        iid = img.get("image_id")
        labels = boxes_by_image.get(iid, [])
        if len(labels) < min_boxes:
            excluded["no_vehicle_boxes"] += 1
            continue
        lic = img.get("license", "")
        if not lic:
            excluded["missing_license"] += 1
            continue
        if not _is_permissive(lic):
            excluded["non_permissive_license"] += 1
            continue
        # sufficient rights metadata = license + author + a source URL
        if not (img.get("author") and (img.get("original_landing_url") or img.get("original_url"))):
            excluded["missing_rights_metadata"] += 1
            continue
        for c in set(labels):
            class_counts[c] += 1
        candidates.append({
            "image_id": iid, "license": lic, "author": img.get("author"),
            "source_url": img.get("original_landing_url") or img.get("original_url"),
            "title": img.get("title", ""), "classes": sorted(set(labels)),
            "box_count": len(labels),
            "approval": "PENDING_HUMAN_LEGAL_REVIEW",   # never auto-approved
        })

    return {
        "candidate_count": len(candidates),
        "candidates": candidates,
        "class_counts": class_counts,
        "excluded": excluded,
        "rights_status": "LICENSE_UNCLEAR",  # pending — NOT production-eligible
        "note": ("Metadata-only candidates. Google disclaims per-image license accuracy; "
                 "a human/legal spot-check is REQUIRED before any production eligibility."),
    }

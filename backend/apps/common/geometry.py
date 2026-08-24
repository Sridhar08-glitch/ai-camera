"""
Geometry validation (Phase 3 §19 / ADR-020). Plain-PostgreSQL, PostGIS-ready.

Validators raise django.core.exceptions.ValidationError. Stored geometry is a dict:
  {"space": "<geo|image_normalized>", "coordinates": [[a, b], ...]}
- geo coordinates are [lng, lat] (GeoJSON order); lat/lng range-checked.
- image_normalized coordinates are [x, y] in 0..1.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError

from apps.common.coordinatespace import CoordinateSpace

# Guardrails against oversized payloads / DoS.
MAX_VERTICES = 512
LAT_MIN, LAT_MAX = -90.0, 90.0
LNG_MIN, LNG_MAX = -180.0, 180.0


def validate_lat(value: float) -> None:
    if value is None or not (LAT_MIN <= float(value) <= LAT_MAX):
        raise ValidationError(f"latitude {value} out of range [{LAT_MIN}, {LAT_MAX}]")


def validate_lng(value: float) -> None:
    if value is None or not (LNG_MIN <= float(value) <= LNG_MAX):
        raise ValidationError(f"longitude {value} out of range [{LNG_MIN}, {LNG_MAX}]")


def validate_bearing(value: int) -> None:
    if value is None or not (0 <= int(value) <= 359):
        raise ValidationError("bearing must be in [0, 359] degrees")


def _coords(geometry: dict) -> list:
    if not isinstance(geometry, dict):
        raise ValidationError("geometry must be an object with 'space' and 'coordinates'")
    space = geometry.get("space")
    coords = geometry.get("coordinates")
    if space not in CoordinateSpace.values:
        raise ValidationError(f"unknown coordinate space: {space!r}")
    if not isinstance(coords, list) or not coords:
        raise ValidationError("coordinates must be a non-empty list")
    if len(coords) > MAX_VERTICES:
        raise ValidationError(f"too many vertices ({len(coords)} > {MAX_VERTICES})")
    for pt in coords:
        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
            raise ValidationError("each coordinate must be a [a, b] pair")
    return coords


def _check_point_space(space: str, a: float, b: float) -> None:
    if space == CoordinateSpace.GEO:
        validate_lng(a)  # GeoJSON order: [lng, lat]
        validate_lat(b)
    elif space == CoordinateSpace.IMAGE_NORMALIZED:
        for v in (a, b):
            if not (0.0 <= float(v) <= 1.0):
                raise ValidationError(f"normalized coordinate {v} out of range [0, 1]")
    else:
        raise ValidationError(f"coordinate space {space} not storable in Phase 3")


def _no_duplicate_consecutive(coords: list) -> None:
    for i in range(1, len(coords)):
        if list(coords[i]) == list(coords[i - 1]):
            raise ValidationError("duplicate consecutive points are not allowed")


def validate_geometry(geometry: dict, *, expected_space: str, kind: str) -> None:
    """kind: 'polygon' | 'line' | 'polyline'."""
    coords = _coords(geometry)
    space = geometry["space"]
    if space != expected_space:
        raise ValidationError(f"expected coordinate space {expected_space}, got {space}")
    for a, b in coords:
        _check_point_space(space, a, b)
    _no_duplicate_consecutive(coords)

    if kind == "polygon":
        # A ring needs >= 3 distinct vertices.
        distinct = {tuple(p) for p in coords}
        if len(distinct) < 3:
            raise ValidationError("polygon requires at least 3 distinct vertices")
    elif kind == "line":
        if len(coords) != 2:
            raise ValidationError("line must have exactly 2 points")
        if list(coords[0]) == list(coords[1]):
            raise ValidationError("line endpoints must differ (degenerate line)")
    elif kind == "polyline":
        if len(coords) < 2:
            raise ValidationError("polyline requires at least 2 points")


def validate_point_dict(point: dict, *, space: str = CoordinateSpace.IMAGE_NORMALIZED) -> None:
    """Validate a single {'x': .., 'y': ..} normalized point (counting-line endpoints)."""
    if not isinstance(point, dict) or "x" not in point or "y" not in point:
        raise ValidationError("point must be an object with 'x' and 'y'")
    _check_point_space(space, point["x"], point["y"])

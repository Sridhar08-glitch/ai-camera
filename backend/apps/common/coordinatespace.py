"""
Canonical coordinate-space vocabulary (Phase 3 / ADR-020).

Geographic (WGS84 lat/lng), image-normalized (0..1 camera-frame), and a reserved
world/local space for FUTURE calibration (not implemented in Phase 3). These are
fundamentally different spaces and must never be mixed.
"""
from __future__ import annotations

from django.db import models


class CoordinateSpace(models.TextChoices):
    GEO = "geo", "Geographic (WGS84 lat/lng)"
    IMAGE_NORMALIZED = "image_normalized", "Image-frame normalized (0..1)"
    WORLD = "world", "World/local (reserved — future calibration)"

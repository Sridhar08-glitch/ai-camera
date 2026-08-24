"""Checksum + config-hash helpers for governance reproducibility."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from django.conf import settings


def canonical_config_hash(config: Any) -> str:
    """Deterministic sha256 of a JSON-serializable config (stable key order)."""
    blob = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def validate_artifact_path(path: str) -> str:
    """
    Ensure an artifact path is inside the configured ARTIFACT_ROOT (no traversal).
    Returns the normalized absolute path or raises ValueError.
    """
    root = Path(getattr(settings, "ARTIFACT_ROOT", "")).resolve()
    if not str(root):
        raise ValueError("ARTIFACT_ROOT is not configured.")
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Artifact path escapes ARTIFACT_ROOT.") from exc
    return str(candidate)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

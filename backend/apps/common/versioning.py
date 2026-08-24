"""Deterministic canonical hashing for configuration versioning (ADR-021)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_hash(payload: Any) -> str:
    """sha256 over a stable JSON serialization (sorted keys, compact separators)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

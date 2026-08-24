"""
Phase 6T training package — ISOLATED from the production backend.

Runs in `training/.venv` (PyTorch). The production runtime (`backend/`) never
imports this package and stays ONNX-Runtime-only (ADR-033). Nothing here trains a
production model or downloads third-party weights by default; the first real model
starts from random initialization (ADR-030).
"""
from __future__ import annotations

# Bumped whenever training code changes in a way that affects reproducibility.
CODE_VERSION = "6t-a.1"

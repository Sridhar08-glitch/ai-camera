"""Phase 6T-A — train/serve preprocessing parity (ADR-037).

The training letterbox MUST match the production runtime letterbox byte-for-byte.
This asserts the SAME golden hash as the backend test
(tests/test_preprocess_bilinear.py::GOLDEN_LETTERBOX_SHA256). If either side drifts,
one of the two golden tests fails.
"""
from __future__ import annotations

import hashlib

import numpy as np

from training.preprocess import PREPROCESS_CONTRACT_VERSION, letterbox

# Must equal backend GOLDEN_LETTERBOX_SHA256 (identical bilinear letterbox contract).
GOLDEN_LETTERBOX_SHA256 = "2f72c602aa15a69cfe501d7455edfef23f766b6b84bb6a137d4fe81607fcad48"


def _fixed_frame():
    return (np.arange(48 * 64 * 3, dtype=np.uint8) % 251).reshape(48, 64, 3)


def test_contract_version():
    assert PREPROCESS_CONTRACT_VERSION == "preproc-v2-bilinear"


def test_letterbox_matches_backend_golden():
    tensor, _ = letterbox(_fixed_frame(), 128)
    digest = hashlib.sha256(np.ascontiguousarray(tensor).tobytes()).hexdigest()
    assert digest == GOLDEN_LETTERBOX_SHA256, (
        "training letterbox diverged from the production runtime contract (train/serve skew)"
    )

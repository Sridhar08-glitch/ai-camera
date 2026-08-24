# ADR-037 — Preprocessing Interpolation Contract (bilinear, train == serve)

**Status:** Accepted (Phase 6T-A)

## Context
A detector trained under one input preprocessing but served under another suffers train/serve
skew. Phase 6 originally used **nearest-neighbour** letterbox resize (an infra placeholder,
acceptable only because it fed the TEST provider / const graph). Before any real model is
trained, the interpolation must be unified and frozen.

## Decision
- The canonical letterbox interpolation is **bilinear** (half-pixel centers,
  `align_corners=False`), pad value **114**, RGB, `/255`, NCHW float32. Contract id:
  **`preproc-v2-bilinear`**.
- **Both** the production runtime (`apps.processing.runtime.detector.preprocess`) and the
  training package (`training.preprocess`) implement the **identical** bilinear letterbox.
  Because the two live in separate environments, they are kept in sync by a **shared golden
  hash** asserted in both test suites (`test_preprocess_bilinear.py` and
  `training/tests/test_preprocess_parity.py`); drift on either side fails a test.
- The letterbox **geometry** (scale, pad_x, pad_y) is interpolation-independent, so
  reverse-letterbox and all Phase 6 coordinate contracts are unchanged — the full 297-test
  Phase 6 baseline stayed green through the change.
- The interpolation is recorded in the exported model's metadata (`interpolation`,
  `preprocess_contract`) so an artifact declares the exact preprocessing it was trained under.

## Consequences
No train/serve preprocessing skew. Bilinear improves small/distant-object fidelity (a core
requirement) versus nearest-neighbour. Any future change to this contract is an explicit,
approved, versioned change requiring both golden hashes + model metadata to be updated.

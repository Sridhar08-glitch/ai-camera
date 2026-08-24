# ADR-036 — Training Checkpoint vs Deployment Artifact Boundary

**Status:** Accepted (Phase 6T-A)

## Context
Training checkpoints and the deployed model are different trust artifacts. Checkpoints are
framework-native and internal; the deployed artifact must be a validated, safe-to-load ONNX
file. Confusing the two would either leak framework coupling into production or risk loading
untrusted serialized code.

## Decision
- **Checkpoints (`training.checkpoint`)** are **state dicts only** (model + optimizer +
  scheduler + AMP scaler + EMA + epoch + global step + best metric + RNG state + config +
  provenance) — never pickled arbitrary Python objects. They are **trusted internal
  artifacts**: no user upload/exec path exists. They enable full mid-run **resume**
  (verified) so long runs survive interruption without restarting at epoch 0.
- **Deployment artifact** is **ONNX only**. Production loads it exclusively through the Phase 6
  `OnnxDetector`, which already validates it (ARTIFACT_ROOT confinement, sha256, ONNX
  magic-byte sniff that rejects pickles — ADR-032). A checkpoint is never a production
  artifact; only an exported, parity-checked ONNX is.
- **Promotion requires parity:** PyTorch↔ONNX parity within documented tolerance is a
  precondition to registering/activating the ONNX artifact (a failed parity check is not a
  successful export).

## Consequences
The training framework stays out of production; the production loader only ever sees a
validated ONNX file. Interrupted training resumes cheaply; no arbitrary code is deserialized
at serve time.

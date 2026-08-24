# ADR-032 — ONNX Artifact & Loading Lifecycle

**Status:** Accepted (Phase 6)

## Context
Loading a model file into an inference runtime is a trust boundary: the file must be the
governed artifact, unmodified, of the right format, and attached to a model version whose
lifecycle permits production use. We must never deserialize an arbitrary/pickled blob, and
we must never *pretend* to use a GPU we don't have.

## Decision
**Production inference boundary = ONNX Runtime.** `OnnxDetector` creates an
`onnxruntime.InferenceSession` from a *validated* ONNX file with an execution-provider
list derived from device policy, and reports the EP ORT actually bound.

**Lifecycle promotion (`ModelLifecycle`, governance):**
`draft → training → evaluated → candidate → approved → active → retired`, plus
`test_only`. Gate enforced in `apps.governance.views`:
- Only **APPROVED** versions may be **activated**; activation demotes the prior active to
  APPROVED; one active version per family (audited `MODEL_APPROVED` / `MODEL_ACTIVATED`).
- **TEST_ONLY can never be approved or activated** for production.

**Artifact validation before load (`detector/artifact.py`):** an artifact is loadable for
production only if it is (1) referenced by a governed `ModelArtifact` of kind `weights`,
(2) resolved **inside `ARTIFACT_ROOT`** via `validate_artifact_path` (no traversal),
(3) present + non-empty + size-consistent, (4) **sha256-consistent** with the recorded
checksum, (5) an **ONNX container** (magic-byte sniff that also rejects pickle opcodes —
we never unpickle), and (6) attached to an APPROVED/ACTIVE (not TEST_ONLY) version.

**Device policy & truthful EP reporting (`detector/device.py`):**
`REQUIRE_GPU | PREFER_GPU | CPU_ONLY` (setting `CV_DETECTOR_DEVICE_POLICY`, default
PREFER_GPU). The requested EP list is intersected with `ort.get_available_providers()` and
the GPUManager device; after the session exists, `actual_ep = session.get_providers()[0]`
is recorded. On the installed **CPU** onnxruntime build there is no CUDA EP, so PREFER_GPU
falls back to CPU **honestly** and REQUIRE_GPU **fails loudly** — never a fake GPU.

**Load ownership:** only the CV runtime loads a model, once per session, reused across
frames, released on teardown. Django/Celery never load (frozen §14).

**Project-created TEST artifact (`detector/testkit.py`):** a minimal, deterministic ONNX
graph (constant `(N,6)` detections, `phase6-infra-v1` output contract) lets us verify the
ONNX Runtime boundary with a **real `InferenceSession`** — no third-party weights. It is
only ever registered as a TEST_ONLY version.

## Consequences
- A tampered, mis-sized, non-ONNX, unapproved, or TEST_ONLY artifact cannot be loaded as
  production (all covered by failure tests).
- GPU acceleration requires `onnxruntime-gpu` + cuDNN (not installed); the design already
  reports and enforces this truthfully, so enabling it later is configuration, not code.
- Phase 6T swaps the constant TEST graph for a governed trained ONNX with no boundary
  change.

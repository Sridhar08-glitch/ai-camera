"""
ONNX artifact validation + resolution (Phase 6 / §19, ADR-032).

Before the CV runtime loads any model file it must prove the file is:
  * referenced by a governed `ModelArtifact` row,
  * physically inside ARTIFACT_ROOT (no path traversal),
  * present, non-empty, and size-consistent,
  * checksum-consistent with the recorded sha256 (integrity / no tamper),
  * an ONNX container (magic-byte sniff — we never unpickle),
  * attached to an AIModelVersion whose lifecycle permits production use.

A TEST_ONLY (or unapproved) version can never be resolved for production loading.
This module performs NO inference and imports no ML framework.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.governance.checksums import sha256_file, validate_artifact_path
from apps.governance.models import ArtifactKind, ModelArtifact, ModelLifecycle
from apps.processing.runtime.detector.contract import DetectionError

# Lifecycle states from which a model may be loaded for PRODUCTION detection.
_PRODUCTION_OK = frozenset({ModelLifecycle.APPROVED, ModelLifecycle.ACTIVE})


@dataclass(frozen=True)
class ResolvedArtifact:
    path: str                 # absolute, validated to live under ARTIFACT_ROOT
    checksum_sha256: str
    size_bytes: int
    model_version_id: str
    model_version_label: str
    provenance: str


def _sniff_onnx(path: str) -> bool:
    """Cheap ONNX container sniff. ONNX is a protobuf; the file starts with the
    `ir_version` field (tag 0x08). We reject obvious non-protobuf/pickle blobs
    without importing onnx. A deeper structural check happens at session build."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(2)
    except OSError:
        return False
    if not head:
        return False
    # Reject python pickle opcodes (0x80 proto, '(' 0x28) up front — never unpickle.
    if head[0] == 0x80:
        return False
    # ONNX ModelProto: first field is ir_version (field #1, varint) → tag byte 0x08.
    return head[0] == 0x08


def resolve_onnx_artifact(
    artifact: ModelArtifact,
    *,
    require_production: bool = True,
) -> ResolvedArtifact:
    """Validate a governed weights artifact and return its resolved location.

    Raises `DetectionError` (code among model_not_approved / artifact_missing /
    checksum_mismatch / invalid_artifact) on any failure. When `require_production`
    is True the model version must be APPROVED/ACTIVE and not TEST_ONLY.
    """
    version = artifact.model_version
    status = version.status

    if require_production:
        if status == ModelLifecycle.TEST_ONLY:
            raise DetectionError(
                "model_not_approved",
                f"model version {version.version} is TEST_ONLY — never loadable as production",
            )
        if status not in _PRODUCTION_OK:
            raise DetectionError(
                "model_not_approved",
                f"model version {version.version} status={status} is not APPROVED/ACTIVE",
            )

    if artifact.kind != ArtifactKind.WEIGHTS:
        raise DetectionError("invalid_artifact", f"artifact kind must be weights, got {artifact.kind}")

    # Resolve + confine under ARTIFACT_ROOT.
    try:
        abs_path = validate_artifact_path(artifact.path)
    except ValueError as exc:
        raise DetectionError("invalid_artifact", str(exc)) from exc

    p = Path(abs_path)
    if not p.is_file():
        raise DetectionError("artifact_missing", f"artifact file not found: {abs_path}")

    size = p.stat().st_size
    if size == 0:
        raise DetectionError("invalid_artifact", "artifact file is empty")
    if artifact.size_bytes is not None and int(artifact.size_bytes) != size:
        raise DetectionError(
            "invalid_artifact",
            f"artifact size mismatch: recorded {artifact.size_bytes}, on-disk {size}",
        )

    if not _sniff_onnx(abs_path):
        raise DetectionError("invalid_artifact", "file is not an ONNX container (or is a pickle)")

    if artifact.checksum_sha256:
        digest = sha256_file(abs_path)
        if digest != artifact.checksum_sha256:
            raise DetectionError(
                "checksum_mismatch",
                f"sha256 mismatch: recorded {artifact.checksum_sha256[:12]}…, computed {digest[:12]}…",
            )

    return ResolvedArtifact(
        path=abs_path,
        checksum_sha256=artifact.checksum_sha256 or "",
        size_bytes=size,
        model_version_id=str(version.id),
        model_version_label=version.version,
        provenance=version.provenance,
    )

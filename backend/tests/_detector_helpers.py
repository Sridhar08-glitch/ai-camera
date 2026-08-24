"""Helpers for Phase 6 detector tests: build a governed ONNX model version + a real
on-disk TEST ONNX artifact under ARTIFACT_ROOT (no third-party weights)."""
from __future__ import annotations

import os

from apps.governance.checksums import sha256_file
from apps.governance.models import (
    AIModel,
    AIModelVersion,
    ArtifactKind,
    ModelArtifact,
    ModelLifecycle,
)
from apps.processing.runtime.detector.testkit import TEST_CLASS_MAP, write_test_onnx


def make_onnx_model_version(
    artifact_root: str,
    *,
    status: str = ModelLifecycle.APPROVED,
    is_active: bool = False,
    input_size: int = 640,
    rel_path: str = "models/test_detector.onnx",
    corrupt_checksum: bool = False,
    size_override: int | None = None,
) -> AIModelVersion:
    """Write a real TEST ONNX under ARTIFACT_ROOT and register a governed version."""
    abs_path = os.path.join(artifact_root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    write_test_onnx(abs_path, target=input_size)
    checksum = sha256_file(abs_path)
    if corrupt_checksum:
        checksum = "0" * 64
    size = size_override if size_override is not None else os.path.getsize(abs_path)

    model = AIModel.objects.create(family="phase6-test-detector", task="detection",
                                   provider="platform")
    version = AIModelVersion.objects.create(
        model=model, version="test-1", provenance="platform_trained",
        status=status, is_active=is_active,
        class_map=TEST_CLASS_MAP, input_spec={"input_size": input_size},
    )
    ModelArtifact.objects.create(
        model_version=version, kind=ArtifactKind.WEIGHTS, path=rel_path,
        checksum_sha256=checksum, size_bytes=size,
    )
    return version

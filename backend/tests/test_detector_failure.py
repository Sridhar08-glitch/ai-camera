"""Phase 6 — detector failure & safety tests (the production gate).

Proves the runtime refuses to load TEST_ONLY / unapproved / tampered / missing
artifacts as production, honors REQUIRE_GPU truthfully, and never silently binds a
model when none is active. No third-party weights.
"""
from __future__ import annotations

import os

import pytest

from apps.governance.models import ModelLifecycle
from apps.processing.runtime.detector.artifact import resolve_onnx_artifact
from apps.processing.runtime.detector.contract import DetectionError
from apps.processing.runtime.detector.device import DevicePolicy, DeviceResolutionError
from apps.processing.runtime.detector.factory import build_provider
from tests._detector_helpers import make_onnx_model_version

pytestmark = pytest.mark.django_db


def _artifact_of(version):
    return version.artifacts.first()


def test_test_only_version_never_loads_as_production(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT, status=ModelLifecycle.TEST_ONLY)
    with pytest.raises(DetectionError) as exc:
        resolve_onnx_artifact(_artifact_of(version), require_production=True)
    assert exc.value.code == "model_not_approved"


def test_unapproved_draft_version_rejected(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT, status=ModelLifecycle.DRAFT)
    with pytest.raises(DetectionError) as exc:
        resolve_onnx_artifact(_artifact_of(version), require_production=True)
    assert exc.value.code == "model_not_approved"


def test_checksum_mismatch_rejected(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT, corrupt_checksum=True)
    with pytest.raises(DetectionError) as exc:
        resolve_onnx_artifact(_artifact_of(version), require_production=True)
    assert exc.value.code == "checksum_mismatch"


def test_size_mismatch_rejected(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT, size_override=999999)
    with pytest.raises(DetectionError) as exc:
        resolve_onnx_artifact(_artifact_of(version), require_production=True)
    assert exc.value.code == "invalid_artifact"


def test_missing_file_rejected(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT)
    art = _artifact_of(version)
    os.remove(os.path.join(settings.ARTIFACT_ROOT, art.path))
    with pytest.raises(DetectionError) as exc:
        resolve_onnx_artifact(art, require_production=True)
    assert exc.value.code == "artifact_missing"


def test_pickle_disguised_as_onnx_rejected(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT)
    art = _artifact_of(version)
    # Overwrite the file with a python pickle header — must be refused (never unpickled).
    path = os.path.join(settings.ARTIFACT_ROOT, art.path)
    with open(path, "wb") as fh:
        fh.write(b"\x80\x04pickle-payload")
    # size + checksum recorded for the real onnx no longer match → invalid before sniff,
    # so clear them to isolate the container sniff.
    art.checksum_sha256 = ""
    art.size_bytes = None
    art.save(update_fields=["checksum_sha256", "size_bytes"])
    with pytest.raises(DetectionError) as exc:
        resolve_onnx_artifact(art, require_production=True)
    assert exc.value.code == "invalid_artifact"


def test_build_provider_no_active_model(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    # An APPROVED-but-not-active model exists; omitted selector must NOT silently use it.
    make_onnx_model_version(settings.ARTIFACT_ROOT, is_active=False)
    with pytest.raises(DetectionError) as exc:
        build_provider({}, "cpu")
    assert exc.value.code == "no_active_model"


def test_build_provider_unknown_model(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    import uuid
    with pytest.raises(DetectionError) as exc:
        build_provider({"model_version_id": str(uuid.uuid4())}, "cpu")
    assert exc.value.code == "model_not_found"


def test_require_gpu_policy_blocks_on_cpu_build(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    settings.CV_DETECTOR_DEVICE_POLICY = "REQUIRE_GPU"
    make_onnx_model_version(settings.ARTIFACT_ROOT, is_active=True)
    # No CUDA EP in the CPU onnxruntime build → honest hard failure, never a fake GPU.
    with pytest.raises(DeviceResolutionError):
        build_provider({"model_version_id": "test"}, "cuda:0")


def test_test_provider_bypasses_production_gate(settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    settings.CV_DETECTOR_DEVICE_POLICY = "CPU_ONLY"
    resolved = build_provider({"model_version_id": "test"}, "cpu")
    assert resolved.is_test_provider is True
    assert resolved.model_version is None
    resolved.provider.unload()

"""
Detector provider resolution (Phase 6 / §23). CV-runtime side only.

Turns a validated `detector` params block + a GPUManager device tag into a loaded
`DetectorProvider`, honoring the production gate:

  * "test"            → DeterministicTestProvider (TEST_ONLY, never real AI).
  * <model_version_id>→ that governed version (must be APPROVED/ACTIVE, not TEST_ONLY).
  * omitted           → the currently ACTIVE detection model version.

Django/Celery never call this; only the CV runtime loads a model (frozen §14).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from apps.governance.models import (
    AIModelVersion,
    ArtifactKind,
    ModelLifecycle,
    ModelTask,
)
from apps.processing.runtime.detector.artifact import resolve_onnx_artifact
from apps.processing.runtime.detector.contract import DetectionError
from apps.processing.runtime.detector.device import (
    DevicePolicy,
    ResolvedDevice,
    resolve_device,
)
from apps.processing.runtime.detector.onnx_backend import OnnxDetector
from apps.processing.runtime.detector.test_provider import DeterministicTestProvider

TEST_SELECTOR = "test"


@dataclass
class ResolvedProvider:
    provider: object                 # DetectorProvider
    device: ResolvedDevice
    model_version: Optional[AIModelVersion]   # None for the test provider
    is_test_provider: bool


def _thresholds(detector_params: dict) -> tuple[float, float]:
    conf = detector_params.get("conf", settings.CV_DETECTOR_CONF_THRESHOLD)
    iou = detector_params.get("iou", settings.CV_DETECTOR_IOU_THRESHOLD)
    return float(conf), float(iou)


def _active_detection_version() -> AIModelVersion:
    version = (
        AIModelVersion.objects.select_related("model")
        .filter(model__task=ModelTask.DETECTION, status=ModelLifecycle.ACTIVE, is_active=True)
        .first()
    )
    if version is None:
        raise DetectionError(
            "no_active_model",
            "no ACTIVE detection model version is configured; select the test provider "
            "explicitly or activate a governed model",
        )
    return version


def _build_onnx(version: AIModelVersion, device: ResolvedDevice, detector_params: dict) -> OnnxDetector:
    artifact = (
        version.artifacts.filter(kind=ArtifactKind.WEIGHTS).order_by("-created_at").first()
    )
    if artifact is None:
        raise DetectionError("artifact_missing", f"model version {version.version} has no weights artifact")
    resolved = resolve_onnx_artifact(artifact, require_production=True)

    class_map = version.class_map or {}
    if not class_map:
        raise DetectionError("invalid_artifact", f"model version {version.version} has no class_map")

    input_size = int((version.input_spec or {}).get("input_size", settings.CV_DETECTOR_INPUT_SIZE))
    conf, iou = _thresholds(detector_params)
    return OnnxDetector(
        onnx_path=resolved.path,
        class_map={int(k): int(v) for k, v in class_map.items()},
        provider_name=version.model.family or "onnx",
        provider_version=version.version,
        input_size=input_size,
        conf_threshold=conf,
        iou_threshold=iou,
        max_detections=settings.CV_DETECTOR_MAX_DETECTIONS,
    )


def build_provider(detector_params: dict, device_tag: str) -> ResolvedProvider:
    """Resolve + load a detector provider. Raises DetectionError / DeviceResolutionError."""
    detector_params = detector_params or {}
    policy = DevicePolicy.parse(settings.CV_DETECTOR_DEVICE_POLICY)
    device = resolve_device(policy, device_tag)  # may raise for REQUIRE_GPU

    selector = detector_params.get("model_version_id")

    if selector == TEST_SELECTOR:
        provider = DeterministicTestProvider()
        provider.load(device)
        return ResolvedProvider(provider=provider, device=device,
                                model_version=None, is_test_provider=True)

    if selector:
        version = (
            AIModelVersion.objects.select_related("model").filter(pk=selector).first()
        )
        if version is None:
            raise DetectionError("model_not_found", f"model version {selector} not found")
        if version.model.task != ModelTask.DETECTION:
            raise DetectionError("invalid_model", f"model version {selector} is not a detection model")
    else:
        version = _active_detection_version()

    provider = _build_onnx(version, device, detector_params)
    provider.load(device)
    provider.warmup()
    return ResolvedProvider(provider=provider, device=device,
                            model_version=version, is_test_provider=False)

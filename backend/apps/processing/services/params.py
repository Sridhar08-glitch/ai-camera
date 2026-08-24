"""Validation + normalization of immutable execution parameters (Phase 5 §9)."""
from __future__ import annotations

from apps.processing.runtime.processors.infra import _REGISTRY as PROCESSORS
from apps.processing.states import SamplingMode

PARAMS_VERSION = 1
_VALID_MODES = {m for m, _ in SamplingMode.choices}


class ParamsError(ValueError):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


def normalize_params(raw: dict | None) -> dict:
    """Return a canonical, validated processing_params dict. Rejects unknown keys."""
    raw = raw or {}
    allowed_top = {"sampling", "processor", "device_preference", "detector"}
    extra = set(raw) - allowed_top
    if extra:
        raise ParamsError("invalid_params", f"unknown keys: {sorted(extra)}")

    sampling = raw.get("sampling") or {}
    if not isinstance(sampling, dict):
        raise ParamsError("invalid_params", "sampling must be an object")
    extra_s = set(sampling) - {"mode", "n", "target_fps"}
    if extra_s:
        raise ParamsError("invalid_params", f"unknown sampling keys: {sorted(extra_s)}")

    mode = sampling.get("mode", SamplingMode.EVERY_FRAME)
    if mode not in _VALID_MODES:
        raise ParamsError("invalid_params", f"invalid sampling mode '{mode}'")

    n = sampling.get("n", 1)
    if mode == SamplingMode.EVERY_N:
        if not isinstance(n, int) or n < 1:
            raise ParamsError("invalid_params", "sampling.n must be a positive integer")
    target_fps = sampling.get("target_fps")
    if mode == SamplingMode.TARGET_FPS:
        if not isinstance(target_fps, (int, float)) or target_fps <= 0:
            raise ParamsError("invalid_params", "sampling.target_fps must be > 0")

    processor = raw.get("processor", "noop")
    if processor not in PROCESSORS:
        raise ParamsError("invalid_params", f"unknown processor '{processor}'")

    device_pref = raw.get("device_preference", "auto")
    if device_pref != "auto" and device_pref != "cpu" and not str(device_pref).startswith("cuda"):
        raise ParamsError("invalid_params", "device_preference must be auto|cpu|cuda[:n]")

    detector = _normalize_detector(raw.get("detector"), processor)

    result = {
        "sampling": {
            "mode": mode,
            "n": int(n) if mode == SamplingMode.EVERY_N else 1,
            "target_fps": float(target_fps) if mode == SamplingMode.TARGET_FPS else None,
        },
        "processor": processor,
        "device_preference": device_pref,
        "params_version": PARAMS_VERSION,
    }
    if detector is not None:
        result["detector"] = detector
    return result


def _normalize_detector(raw_detector, processor) -> dict | None:
    """Validate the optional detector block (Phase 6). Only meaningful for the
    'detector' processor. `model_version_id` = 'test' selects the deterministic
    TEST provider; a UUID string selects a governed model; omission uses the
    ACTIVE detection model at runtime."""
    if raw_detector is None:
        if processor == "detector":
            # Default to the explicit, safe TEST provider so an unconfigured detector
            # session is runnable without silently binding a production model.
            return {"model_version_id": "test"}
        return None
    if processor != "detector":
        raise ParamsError("invalid_params", "detector block is only valid for the 'detector' processor")
    if not isinstance(raw_detector, dict):
        raise ParamsError("invalid_params", "detector must be an object")
    extra = set(raw_detector) - {"model_version_id", "conf", "iou"}
    if extra:
        raise ParamsError("invalid_params", f"unknown detector keys: {sorted(extra)}")

    out: dict = {}
    mvid = raw_detector.get("model_version_id", "test")
    if not isinstance(mvid, str) or not mvid:
        raise ParamsError("invalid_params", "detector.model_version_id must be a non-empty string ('test' or a model version id)")
    out["model_version_id"] = mvid

    for key in ("conf", "iou"):
        if key in raw_detector:
            v = raw_detector[key]
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0.0 <= float(v) <= 1.0):
                raise ParamsError("invalid_params", f"detector.{key} must be a float in [0,1]")
            out[key] = float(v)
    return out

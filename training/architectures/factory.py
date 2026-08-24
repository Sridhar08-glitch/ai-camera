"""
Architecture factory (Phase 6T-A / D3/D4). Random initialization only — NO
third-party pretrained weights (ADR-030).

- "tiny"    → TinyDetector (smoke/plumbing; raw grid output + `tiny_v1` adapter).
- "fcos"    → torchvision FCOS ResNet50-FPN, `weights=None, weights_backbone=None`
              (random init, BSD-3, in-stack, no download) — the first-class D3
              fallback integrated in THIS environment.
- "yolox_s" → intended D3 primary; requires the pinned YOLOX training dependency,
              which could not be installed here because the CUDA wheel index /
              YOLOX ecosystem was unreachable (offline env). Raises with guidance so
              the limitation is explicit, not silent.
"""
from __future__ import annotations

import torch.nn as nn

from training.architectures.tiny import TinyDetector


def build_detector(name: str, *, num_classes: int = 6) -> nn.Module:
    key = (name or "tiny").lower()
    if key == "tiny":
        return TinyDetector(num_classes=num_classes)
    if key == "fcos":
        import torchvision
        # random init, no downloads — explicit no-pretrained-weights policy.
        return torchvision.models.detection.fcos_resnet50_fpn(
            weights=None, weights_backbone=None, num_classes=num_classes
        )
    if key in ("yolox_s", "yolox"):
        raise NotImplementedError(
            "YOLOX-S is the intended D3 primary but requires the pinned YOLOX training "
            "dependency, which is unavailable in this offline environment (the PyTorch "
            "CUDA wheel index was unreachable). Use 'fcos' (integrated fallback) or 'tiny' "
            "(smoke) here; integrate YOLOX on an environment that can reach the package "
            "index — see PHASE_6T_A_VERIFICATION_REPORT.md."
        )
    raise ValueError(f"unknown architecture '{name}'")

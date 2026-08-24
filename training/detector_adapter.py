"""
Detector training adapters (Phase 6T-B). Keep the training loop architecture-
independent: each adapter owns the architecture-specific bits (model construction,
target formatting, training-forward + loss extraction/aggregation, inference-output
normalization, ONNX output schema). The engine never branches on model type.

torchvision detection models differ train vs eval:
  train:  model(images, targets) -> dict[str, Tensor]  (losses)
  eval:   model(images)          -> list[dict[str, Tensor]]  (boxes/scores/labels)
TinyDetector emits a raw grid tensor with a custom loss. Both satisfy the same
adapter interface below.
"""
from __future__ import annotations

from typing import Protocol

import torch
import torch.nn.functional as F

from training.architectures.tiny import TinyDetector
from training.data import build_targets


class DetectorTrainingAdapter(Protocol):
    name: str
    output_schema: str

    def build_model(self, num_classes: int, input_size: int) -> torch.nn.Module: ...
    def compute_loss(self, model, imgs, boxes_list, device) -> tuple: ...
    def infer(self, model, imgs) -> list: ...


# ---------------- TinyDetector ----------------

class TinyTrainingAdapter:
    name = "tiny"
    output_schema = "tiny_v1"

    def build_model(self, num_classes: int, input_size: int) -> torch.nn.Module:
        m = TinyDetector(num_classes=num_classes)
        self._stride = m.stride
        self._grid = m.grid_size(input_size)
        self._num_classes = num_classes
        return m

    def compute_loss(self, model, imgs, boxes_list, device):
        """Sets train mode; returns (total_loss_tensor, {loss_name: float})."""
        model.train()
        target, pos, cidx = build_targets(boxes_list, grid=self._grid, stride=self._stride,
                                          num_classes=self._num_classes, device=device)
        raw = model(imgs)
        obj = F.binary_cross_entropy_with_logits(raw[..., 4], target[..., 4])
        if pos.any():
            box = F.mse_loss(raw[..., 0:4][pos], target[..., 0:4][pos])
            cls = F.cross_entropy(raw[..., 5:][pos], cidx[pos])
        else:
            box = raw.sum() * 0.0
            cls = raw.sum() * 0.0
        total = obj + box + cls
        return total, {"obj": float(obj), "box": float(box), "cls": float(cls)}

    def infer(self, model, imgs):
        model.eval()
        with torch.no_grad():
            return model(imgs)  # raw grid tensor; decode via training.adapter.decode_tiny_v1


# ---------------- torchvision FCOS ----------------

class FcosTrainingAdapter:
    """FCOS ResNet50-FPN, random init. The internal GeneralizedRCNNTransform is made
    (near) identity so it consumes our `preproc-v2-bilinear` letterboxed 640×640 /255
    images directly: image_mean=0, image_std=1, min_size=max_size=input_size. This
    keeps train == serve preprocessing."""

    name = "fcos"
    output_schema = "fcos_v1"

    def build_model(self, num_classes: int, input_size: int) -> torch.nn.Module:
        import torchvision

        self._num_classes = num_classes
        # weights=None + weights_backbone=None → random init, NO pretrained download.
        return torchvision.models.detection.fcos_resnet50_fpn(
            weights=None, weights_backbone=None, num_classes=num_classes,
            min_size=input_size, max_size=input_size,
            image_mean=[0.0, 0.0, 0.0], image_std=[1.0, 1.0, 1.0],
        )

    def _targets(self, boxes_list, device):
        """Convert dataset boxes [K,5]=[cls,x1,y1,x2,y2] → torchvision targets.
        Drops degenerate boxes (x2<=x1 or y2<=y1). labels are canonical class ids
        (0..num_classes-1); torchvision FCOS treats these as foreground classes."""
        targets = []
        for boxes in boxes_list:
            if boxes.numel() == 0:
                targets.append({"boxes": torch.zeros((0, 4), device=device),
                                "labels": torch.zeros((0,), dtype=torch.int64, device=device)})
                continue
            cls = boxes[:, 0].to(torch.int64)
            xyxy = boxes[:, 1:5].float()
            valid = (xyxy[:, 2] > xyxy[:, 0]) & (xyxy[:, 3] > xyxy[:, 1])
            targets.append({"boxes": xyxy[valid].to(device), "labels": cls[valid].to(device)})
        return targets

    def compute_loss(self, model, imgs, boxes_list, device):
        model.train()
        images = [img for img in imgs]                     # FCOS wants a list of CxHxW
        targets = self._targets(boxes_list, device)
        loss_dict = model(images, targets)                 # dict[str, Tensor]
        total = sum(loss_dict.values())
        return total, {k: float(v.detach()) for k, v in loss_dict.items()}

    def infer(self, model, imgs):
        model.eval()
        with torch.no_grad():
            images = [img for img in imgs]
            return model(images)  # list[{boxes,scores,labels}] in input-pixel space


_REGISTRY = {"tiny": TinyTrainingAdapter, "fcos": FcosTrainingAdapter}


def get_training_adapter(name: str) -> DetectorTrainingAdapter:
    key = (name or "tiny").lower()
    if key not in _REGISTRY:
        if key in ("yolox_s", "yolox"):
            raise NotImplementedError(
                "YOLOX-S training adapter not integrated in this environment (see ADR-034); "
                "use 'fcos' (integrated) or 'tiny' (smoke).")
        raise ValueError(f"unknown training architecture '{name}'")
    return _REGISTRY[key]()

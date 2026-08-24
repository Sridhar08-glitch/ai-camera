"""
TinyDetector (Phase 6T-A smoke architecture). Random-init, self-contained, fast.

A minimal single-scale anchor-free head over a small conv stem. It emits a **raw**
YOLO-like grid tensor (NOT the Phase 6 test `(N,6)` contract), so the export path
must go through an architecture-specific adapter (`tiny_v1`) → canonical Detection,
exactly like a real model. This exists only to verify the training/export/parity
plumbing — it is not a real detector.

Raw output shape: (B, S*S, 5 + num_classes) = [tx, ty, tw, th, obj, cls...] per cell.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class TinyDetector(nn.Module):
    def __init__(self, num_classes: int = 6, stride: int = 16, width: int = 32):
        super().__init__()
        self.num_classes = num_classes
        self.stride = stride
        self.out_ch = 5 + num_classes
        self.stem = nn.Sequential(
            nn.Conv2d(3, width, 3, stride=2, padding=1), nn.BatchNorm2d(width), nn.ReLU(),
            nn.Conv2d(width, width, 3, stride=2, padding=1), nn.BatchNorm2d(width), nn.ReLU(),
            nn.Conv2d(width, width * 2, 3, stride=2, padding=1), nn.BatchNorm2d(width * 2), nn.ReLU(),
            nn.Conv2d(width * 2, width * 2, 3, stride=2, padding=1), nn.BatchNorm2d(width * 2), nn.ReLU(),
        )  # total stride 16
        self.head = nn.Conv2d(width * 2, self.out_ch, 1)
        # random init (explicit — no pretrained weights)
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.stem(x)                       # (B, C, S, S)
        out = self.head(feat)                     # (B, out_ch, S, S)
        b, c, gh, gw = out.shape
        out = out.permute(0, 2, 3, 1).reshape(b, gh * gw, c)  # (B, S*S, out_ch)
        return out

    def grid_size(self, input_size: int) -> int:
        return input_size // self.stride

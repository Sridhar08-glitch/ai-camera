"""
Training data plumbing (Phase 6T-A). Wraps the synthetic smoke dataset into a torch
Dataset that yields letterboxed image tensors + target boxes in target-pixel space.
Preprocessing uses the shared bilinear letterbox contract (ADR-037).
"""
from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset

from training.preprocess import letterbox


class SyntheticDetectionDataset(Dataset):
    """Yields (image_tensor[3,T,T] float32, boxes[K,5]) where boxes rows are
    [class_id, x1, y1, x2, y2] in **letterbox target-pixel** coords."""

    def __init__(self, samples: list, input_size: int = 128):
        self.samples = samples
        self.input_size = input_size

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s = self.samples[idx]
        img = s["image"]
        tensor, meta = letterbox(img, self.input_size)  # (1,3,T,T)
        t = torch.from_numpy(tensor[0])                 # (3,T,T)
        rows = []
        for (cls, x1, y1, x2, y2) in s["boxes"]:
            rows.append([
                cls,
                x1 * meta.scale + meta.pad_x, y1 * meta.scale + meta.pad_y,
                x2 * meta.scale + meta.pad_x, y2 * meta.scale + meta.pad_y,
            ])
        boxes = torch.tensor(rows, dtype=torch.float32) if rows else torch.zeros((0, 5))
        return t, boxes


def collate(batch):
    imgs = torch.stack([b[0] for b in batch], dim=0)
    boxes = [b[1] for b in batch]
    return imgs, boxes


def build_targets(boxes_list, *, grid: int, stride: int, num_classes: int, device):
    """Build the TinyDetector target grid (B, S*S, 5+C) + a positive-cell mask.

    Each GT box center falls in one cell (positive): obj=1, box=(dx,dy,log(w/stride),
    log(h/stride)), class index. Empty cells are negatives (obj=0)."""
    B = len(boxes_list)
    n = grid * grid
    target = torch.zeros((B, n, 5 + num_classes), device=device)
    pos_mask = torch.zeros((B, n), dtype=torch.bool, device=device)
    cls_idx = torch.zeros((B, n), dtype=torch.long, device=device)
    for b, boxes in enumerate(boxes_list):
        for row in boxes:
            cls = int(row[0].item())
            x1, y1, x2, y2 = row[1].item(), row[2].item(), row[3].item(), row[4].item()
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            w, h = max(1.0, x2 - x1), max(1.0, y2 - y1)
            j = min(grid - 1, max(0, int(cx // stride)))
            i = min(grid - 1, max(0, int(cy // stride)))
            cell = i * grid + j
            target[b, cell, 0] = (cx / stride) - j
            target[b, cell, 1] = (cy / stride) - i
            target[b, cell, 2] = float(np.log(w / stride))
            target[b, cell, 3] = float(np.log(h / stride))
            target[b, cell, 4] = 1.0
            target[b, cell, 5 + cls] = 1.0
            pos_mask[b, cell] = True
            cls_idx[b, cell] = cls
    return target, pos_mask, cls_idx

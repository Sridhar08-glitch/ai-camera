"""
Evaluation infrastructure (Phase 6T-A / plan §36). Objective detection metrics.

Provides a lightweight IoU-matching precision/recall/mean-IoU evaluator (deterministic,
fixture-testable) plus a pycocotools mAP hook for real evaluation. Model selection is
never on training loss (§37); this module supplies the objective signal.
"""
from __future__ import annotations

import numpy as np


def iou_xyxy(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    ua = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1) + max(0.0, bx2 - bx1) * max(0.0, by2 - by1) - inter
    return inter / ua if ua > 0 else 0.0


def match_and_score(preds, gts, *, iou_thr: float = 0.5) -> dict:
    """Greedy IoU matching. `preds`=[(box_xyxy,score,cls)], `gts`=[(box_xyxy,cls)].
    Returns tp/fp/fn + precision/recall + mean IoU of matches."""
    order = sorted(range(len(preds)), key=lambda i: preds[i][1], reverse=True)
    used = set()
    tp, ious = 0, []
    for i in order:
        pbox, _score, pcls = preds[i]
        best_iou, best_j = 0.0, -1
        for j, (gbox, gcls) in enumerate(gts):
            if j in used or gcls != pcls:
                continue
            v = iou_xyxy(pbox, gbox)
            if v > best_iou:
                best_iou, best_j = v, j
        if best_j >= 0 and best_iou >= iou_thr:
            tp += 1
            used.add(best_j)
            ious.append(best_iou)
    fp = len(preds) - tp
    fn = len(gts) - tp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 4),
            "recall": round(recall, 4), "mean_iou": round(float(np.mean(ious)) if ious else 0.0, 4)}


def coco_map(gt_coco: dict, detections: list) -> dict:
    """pycocotools mAP hook. `detections` = COCO-result list
    [{image_id,category_id,bbox:[x,y,w,h],score}]. Returns mAP@0.5 and @0.5:0.95."""
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    coco_gt = COCO()
    coco_gt.dataset = gt_coco
    coco_gt.createIndex()
    if not detections:
        return {"mAP_50_95": 0.0, "mAP_50": 0.0, "note": "no detections"}
    coco_dt = coco_gt.loadRes(detections)
    ev = COCOeval(coco_gt, coco_dt, iouType="bbox")
    ev.evaluate(); ev.accumulate(); ev.summarize()
    return {"mAP_50_95": float(ev.stats[0]), "mAP_50": float(ev.stats[1])}

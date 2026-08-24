"""
PyTorch <-> ONNX parity (Phase 6T-A / plan §42). A failed parity check is NOT a
successful export — an artifact that materially diverges must never be promoted.

Compares raw outputs and post-adapter decoded detections on identical inputs within
documented tolerances.
"""
from __future__ import annotations

import numpy as np
import torch


def run_parity(model, onnx_path, *, input_size: int, num_classes: int, stride: int,
               output_schema: str = "tiny_v1", n_samples: int = 3,
               raw_tol: float = 1e-3, seed: int = 0) -> dict:
    """Return a parity report. `passed` iff raw outputs agree within `raw_tol`."""
    import onnxruntime as ort

    from training.adapter import ADAPTERS

    model.eval()
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name
    decode = ADAPTERS[output_schema]

    rng = np.random.default_rng(seed)
    max_raw_diff = 0.0
    class_agree = True
    for _ in range(n_samples):
        x = rng.random((1, 3, input_size, input_size)).astype(np.float32)
        with torch.no_grad():
            torch_out = model(torch.from_numpy(x)).cpu().numpy()
        onnx_out = sess.run([out_name], {in_name: x})[0]
        max_raw_diff = max(max_raw_diff, float(np.abs(torch_out - onnx_out).max()))
        _, _, cls_t = decode(torch_out, input_size=input_size, stride=stride, num_classes=num_classes)
        _, _, cls_o = decode(onnx_out, input_size=input_size, stride=stride, num_classes=num_classes)
        if not np.array_equal(cls_t, cls_o):
            class_agree = False

    passed = max_raw_diff <= raw_tol and class_agree
    return {"passed": bool(passed), "max_raw_diff": max_raw_diff,
            "class_agreement": class_agree, "raw_tol": raw_tol, "n_samples": n_samples}


def run_fcos_parity(model, onnx_path, *, input_size: int, n_samples: int = 3,
                    box_tol: float = 1.0, seed: int = 0) -> dict:
    """FCOS parity. Because torchvision bakes score-thresh + NMS into the graph, the
    PARITY BOUNDARY is the FINAL post-NMS detections (not a pre-postprocess tensor).
    Compares detection count and, when non-empty, the max box-coordinate delta of
    score-sorted detections. `passed` iff counts match and box deltas ≤ box_tol."""
    import numpy as np
    import onnxruntime as ort

    model.eval()
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    rng = np.random.default_rng(seed)
    max_box_diff = 0.0
    counts_match = True
    total_dets = 0
    for _ in range(n_samples):
        x = rng.random((3, input_size, input_size)).astype(np.float32)
        with torch.no_grad():
            out = model([torch.from_numpy(x)])[0]
        tb = out["boxes"].cpu().numpy(); ts = out["scores"].cpu().numpy()
        ob, os_, ol = sess.run(None, {in_name: x})
        total_dets += len(tb)
        if len(tb) != len(ob):
            counts_match = False
            continue
        if len(tb):
            ti = ts.argsort()[::-1]; oi = os_.argsort()[::-1]
            max_box_diff = max(max_box_diff, float(np.abs(tb[ti] - ob[oi]).max()))
    passed = counts_match and max_box_diff <= box_tol
    return {"passed": bool(passed), "parity_boundary": "final post-NMS detections",
            "counts_match": counts_match, "max_box_diff": max_box_diff,
            "box_tol": box_tol, "total_torch_dets": total_dets, "n_samples": n_samples,
            "note": "random-init model may emit 0 dets; empty==empty is valid agreement"}

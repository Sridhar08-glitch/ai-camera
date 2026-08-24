"""
ONNX export (Phase 6T-A / plan §40, D16). Fixed, documented I/O contract; validated
with onnx.checker. The exported model carries a raw architecture-native output whose
decode is done by the registered adapter id (§41/§44), NOT the Phase 6 `(N,6)` test
contract.
"""
from __future__ import annotations

import torch


def export_onnx(model, path: str, *, input_size: int, opset: int = 17,
                output_schema: str = "tiny_v1", dynamic_batch: bool = True) -> dict:
    """Export `model` to ONNX. Returns a metadata dict describing the I/O contract."""
    model.eval()
    dummy = torch.zeros((1, 3, input_size, input_size), dtype=torch.float32)
    dynamic_axes = {"images": {0: "batch"}, "output": {0: "batch"}} if dynamic_batch else None
    # Legacy TorchScript exporter (dynamo=False) — stable, no onnxscript dependency,
    # and well-supported for a static CNN graph.
    torch.onnx.export(
        model, dummy, path,
        input_names=["images"], output_names=["output"],
        opset_version=opset, dynamic_axes=dynamic_axes, dynamo=False,
    )
    _validate(path)
    return {
        "path": path,
        "input_name": "images",
        "input_shape": [1, 3, input_size, input_size],
        "input_dtype": "float32",
        "normalization": "/255",
        "channel_order": "RGB",
        "layout": "NCHW",
        "pad_value": 114,
        "interpolation": "bilinear",
        "preprocess_contract": "preproc-v2-bilinear",
        "output_name": "output",
        "output_schema": output_schema,
        "opset": opset,
    }


def export_fcos_onnx(model, path: str, *, input_size: int, opset: int = 17) -> dict:
    """Export a torchvision FCOS model to ONNX. FCOS bakes its transform + postprocess
    (score-thresh + NMS) into the graph, so the exported model takes a single [3,H,W]
    image and emits FINAL detections (boxes/scores/labels) in target-pixel space
    (output schema `fcos_v1`)."""
    model.eval()
    dummy = [torch.rand(3, input_size, input_size, dtype=torch.float32)]
    torch.onnx.export(
        model, (dummy,), path, opset_version=opset, dynamo=False,
        input_names=["images"], output_names=["boxes", "scores", "labels"],
        dynamic_axes={"images": {1: "h", 2: "w"}},
    )
    _validate(path)
    return {
        "path": path, "input_name": "images", "input_shape": [3, input_size, input_size],
        "input_dtype": "float32", "normalization": "/255 (image_mean=0,std=1 baked in)",
        "channel_order": "RGB", "layout": "CHW (no batch dim)", "pad_value": 114,
        "interpolation": "bilinear", "preprocess_contract": "preproc-v2-bilinear",
        "outputs": ["boxes", "scores", "labels"], "postprocess": "score-thresh + NMS in-graph",
        "output_schema": "fcos_v1", "opset": opset,
    }


def _validate(path: str) -> None:
    import onnx

    m = onnx.load(path)
    onnx.checker.check_model(m)

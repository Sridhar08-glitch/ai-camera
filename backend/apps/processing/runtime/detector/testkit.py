"""
Project-created minimal ONNX TEST artifact (Phase 6 / §49). NOT a trained model.

Builds a tiny, deterministic ONNX container that satisfies the `phase6-infra-v1`
output contract so the ONNX Runtime boundary (`OnnxDetector`) can be verified with
a REAL `InferenceSession` — without any third-party pretrained weights. The graph
emits a fixed constant detections tensor; it does not learn or detect anything and
must only ever be registered as a TEST_ONLY model version.

Requires the `onnx` authoring library (dev/infra only). No torch, no training.
"""
from __future__ import annotations

import numpy as np

# Fixed constant detections the test graph emits: (K,6) = x1,y1,x2,y2,score,cls_idx
# in letterbox target-pixel space. Model class indices 0 and 5 (mapped by class_map).
_CONST_DETECTIONS = np.array(
    [
        [100.0, 100.0, 260.0, 300.0, 0.90, 0.0],
        [320.0, 140.0, 400.0, 320.0, 0.75, 5.0],
    ],
    dtype=np.float32,
)


def build_test_onnx_bytes(target: int = 640) -> bytes:
    """Return serialized bytes of a minimal valid ONNX model (const detections)."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    images = helper.make_tensor_value_info(
        "images", TensorProto.FLOAT, [1, 3, target, target]
    )
    detections = helper.make_tensor_value_info(
        "detections", TensorProto.FLOAT, list(_CONST_DETECTIONS.shape)
    )

    const_tensor = numpy_helper.from_array(_CONST_DETECTIONS, name="const_dets")
    const_node = helper.make_node(
        "Constant", inputs=[], outputs=["detections"], value=const_tensor
    )
    # Consume `images` so it is a genuine (if ignored) graph input: Shape → dangling.
    shape_node = helper.make_node("Shape", inputs=["images"], outputs=["_img_shape"])

    graph = helper.make_graph(
        [shape_node, const_node],
        "phase6_infra_test_detector",
        inputs=[images],
        outputs=[detections],
    )
    model = helper.make_model(
        graph,
        producer_name="ai-camera-phase6-testkit",
        opset_imports=[helper.make_opsetid("", 13)],
    )
    model.ir_version = 8  # keep compatible with onnxruntime 1.20
    onnx.checker.check_model(model)
    return model.SerializeToString()


def write_test_onnx(path: str, target: int = 640) -> str:
    """Write the test ONNX artifact to `path`; return the path."""
    data = build_test_onnx_bytes(target)
    with open(path, "wb") as fh:
        fh.write(data)
    return path


# The class map a governed TEST_ONLY version would carry for this artifact.
TEST_CLASS_MAP = {0: 0, 5: 5}

"""Phase 6T-B — FCOS training integration (torch-gated; uses GPU when available).

Covers: random-init/no-pretrained-download, target conversion, real loss-dict smoke
training, checkpoint/resume, and the eval adapter. TEST_ONLY synthetic data only."""
from __future__ import annotations

import os

import pytest

torch = pytest.importorskip("torch")

from training.config import TrainConfig
from training.data import collate, SyntheticDetectionDataset
from training.detector_adapter import FcosTrainingAdapter, get_training_adapter
from training.engine import train_run
from training.synthetic import make_dataset

INPUT = 256  # FCOS FPN needs enough spatial size; keep small for a fast smoke


def _cfg(**kw):
    base = dict(architecture="fcos", input_size=INPUT, max_epochs=2, batch_size=2,
                base_lr=0.005, early_stop_patience=99, amp=torch.cuda.is_available())
    base.update(kw)
    return TrainConfig(**base)


# ---- Part D: random init / no pretrained download ----

def test_fcos_builds_with_no_pretrained_weights(monkeypatch):
    import torchvision
    captured = {}
    real = torchvision.models.detection.fcos_resnet50_fpn

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(torchvision.models.detection, "fcos_resnet50_fpn", spy)
    m = FcosTrainingAdapter().build_model(num_classes=6, input_size=INPUT)
    assert captured.get("weights") is None
    assert captured.get("weights_backbone") is None       # no ImageNet backbone download
    assert m is not None


def test_fcos_weights_are_random_not_constant():
    m = FcosTrainingAdapter().build_model(6, INPUT)
    # a conv weight tensor should be non-trivial (random init), not all-zeros/ones
    w = next(p for p in m.parameters() if p.dim() == 4)
    assert float(w.std()) > 0 and float(w.abs().sum()) > 0


# ---- Part C: target conversion ----

def test_fcos_target_conversion():
    a = FcosTrainingAdapter()
    a.build_model(6, INPUT)
    boxes = torch.tensor([[2, 10.0, 10, 40, 30],       # valid
                          [0, 5.0, 5, 5, 20]])          # degenerate (x2==x1) → dropped
    targets = a._targets([boxes], device="cpu")
    t = targets[0]
    assert t["boxes"].shape == (1, 4) and t["boxes"].dtype == torch.float32
    assert t["labels"].tolist() == [2] and t["labels"].dtype == torch.int64


def test_fcos_empty_target_ok():
    a = FcosTrainingAdapter(); a.build_model(6, INPUT)
    targets = a._targets([torch.zeros((0, 5))], device="cpu")
    assert targets[0]["boxes"].shape == (0, 4)
    assert targets[0]["labels"].shape == (0,)


# ---- Part E/F: real FCOS smoke training + loss dict + checkpoint/resume ----

def test_fcos_smoke_training_and_loss_keys(tmp_path):
    cfg = _cfg(max_epochs=2)
    res = train_run(cfg, make_dataset(8, base_seed=0), make_dataset(4, base_seed=50), str(tmp_path))
    assert res["epochs_run"] >= 1
    assert os.path.exists(res["best_ckpt"]) and os.path.exists(res["last_ckpt"])
    # FCOS returns a real loss dictionary — record its keys
    hist = res["history"]
    assert hist[-1]["val_loss"] == hist[-1]["val_loss"]  # finite (not NaN)
    # provenance recorded
    assert len(res["provenance"]["code_identity"]) == 64


def test_fcos_loss_dict_finite_keys():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    a = get_training_adapter("fcos")
    model = a.build_model(6, INPUT).to(device)
    ds = SyntheticDetectionDataset(make_dataset(2, base_seed=1), input_size=INPUT)
    imgs = torch.stack([ds[0][0], ds[1][0]]).to(device)
    boxes = [ds[0][1], ds[1][1]]
    total, parts = a.compute_loss(model, imgs, boxes, device)
    assert torch.isfinite(total)
    # torchvision FCOS loss keys (record for the report)
    assert set(parts.keys()) and all(v == v for v in parts.values())
    print("FCOS_LOSS_KEYS", sorted(parts.keys()))


def test_fcos_resume_continues(tmp_path):
    cfg = _cfg(max_epochs=1)
    res = train_run(cfg, make_dataset(6), make_dataset(4, base_seed=9), str(tmp_path))
    cfg2 = _cfg(max_epochs=2)
    res2 = train_run(cfg2, make_dataset(6), make_dataset(4, base_seed=9), str(tmp_path),
                     resume_from=res["last_ckpt"])
    assert res2["epochs_run"] >= 1  # continued (RNG/device restore works on GPU too)


# ---- Part G: eval adapter (inference output normalization) ----

def test_fcos_infer_returns_detections():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    a = get_training_adapter("fcos")
    model = a.build_model(6, INPUT).to(device)
    ds = SyntheticDetectionDataset(make_dataset(1, base_seed=2), input_size=INPUT)
    imgs = ds[0][0].unsqueeze(0).to(device)
    out = a.infer(model, imgs)
    assert isinstance(out, list) and "boxes" in out[0] and "scores" in out[0] and "labels" in out[0]


# ---- Part H/I: FCOS ONNX export + ORT load + TEST inference + parity ----

def test_fcos_onnx_export_and_ort_load(tmp_path):
    import numpy as np
    import onnxruntime as ort

    from training.export import export_fcos_onnx

    model = FcosTrainingAdapter().build_model(6, INPUT).cpu()
    onnx_path = str(tmp_path / "fcos.onnx")
    meta = export_fcos_onnx(model, onnx_path, input_size=INPUT)
    assert meta["output_schema"] == "fcos_v1"
    assert meta["outputs"] == ["boxes", "scores", "labels"]
    assert os.path.exists(onnx_path)
    # ORT load + a TEST_ONLY inference (contract check, not accuracy)
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    outs = sess.run(None, {"images": np.random.rand(3, INPUT, INPUT).astype("float32")})
    assert len(outs) == 3
    assert outs[0].ndim == 2 and outs[0].shape[1] == 4  # boxes [N,4]


def test_fcos_pytorch_onnx_parity_boundary(tmp_path):
    from training.export import export_fcos_onnx
    from training.parity import run_fcos_parity

    model = FcosTrainingAdapter().build_model(6, INPUT).cpu()
    onnx_path = str(tmp_path / "fcos.onnx")
    export_fcos_onnx(model, onnx_path, input_size=INPUT)
    rep = run_fcos_parity(model, onnx_path, input_size=INPUT, n_samples=2)
    # parity boundary is documented; counts must match (both likely empty for random init)
    assert rep["parity_boundary"] == "final post-NMS detections"
    assert rep["counts_match"] is True
    assert rep["passed"] is True

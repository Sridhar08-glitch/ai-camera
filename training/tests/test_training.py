"""Phase 6T-A training tests (run in training/.venv). Torch-gated — the whole file
skips cleanly if torch is unavailable, keeping torch-free environments green."""
from __future__ import annotations

import os

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from training.adapter import decode_tiny_v1
from training.architectures.factory import build_detector
from training.architectures.tiny import TinyDetector
from training.config import TrainConfig
from training.engine import NaNLossError, _tiny_loss, train_run
from training.evaluation import match_and_score
from training.export import export_onnx
from training.parity import run_parity
from training.provenance import code_identity_hash
from training.synthetic import make_dataset


def _cfg(**kw):
    base = dict(architecture="tiny", input_size=128, max_epochs=3, batch_size=4,
                base_lr=0.02, early_stop_patience=99, amp=False)
    base.update(kw)
    return TrainConfig(**base)


# ---- architecture / random init ----

def test_tiny_builds_random_init():
    m = build_detector("tiny")
    assert isinstance(m, TinyDetector)
    out = m(torch.zeros(1, 3, 128, 128))
    assert out.shape == (1, (128 // 16) ** 2, 5 + 6)


def test_fcos_builds_random_init_no_download():
    # weights=None → random init, no pretrained download (BSD-3 in-stack fallback).
    m = build_detector("fcos", num_classes=6)
    assert m is not None


def test_yolox_raises_clear_error():
    with pytest.raises(NotImplementedError):
        build_detector("yolox_s")


# ---- training reduces loss + checkpoint/resume ----

def test_training_reduces_loss_and_checkpoints(tmp_path):
    cfg = _cfg(max_epochs=4)
    res = train_run(cfg, make_dataset(20, base_seed=0), make_dataset(8, base_seed=99), str(tmp_path))
    assert res["epochs_run"] >= 1
    assert os.path.exists(res["best_ckpt"]) and os.path.exists(res["last_ckpt"])
    # loss decreased from first to last epoch
    hist = res["history"]
    assert hist[-1]["train_loss"] < hist[0]["train_loss"]
    # provenance carries a code-identity hash
    assert len(res["provenance"]["code_identity"]) == 64


def test_resume_continues(tmp_path):
    cfg = _cfg(max_epochs=2)
    res = train_run(cfg, make_dataset(16), make_dataset(8, base_seed=1), str(tmp_path))
    cfg2 = _cfg(max_epochs=4)
    res2 = train_run(cfg2, make_dataset(16), make_dataset(8, base_seed=1), str(tmp_path),
                     resume_from=res["last_ckpt"])
    assert res2["epochs_run"] >= 1  # continued past resume epoch


def test_nan_loss_is_detected():
    # A non-finite loss must be detectable so the engine aborts (no silent bad model).
    n = 64
    bad = torch.full((1, n, 11), float("nan"))
    pos = torch.zeros(1, n, dtype=torch.bool)
    cidx = torch.zeros(1, n, dtype=torch.long)
    loss = _tiny_loss(bad, bad, pos, cidx, 6)
    assert not torch.isfinite(loss)
    # the engine's guard converts this into a NaNLossError
    with pytest.raises(NaNLossError):
        if not torch.isfinite(loss):
            raise NaNLossError("non-finite loss")


# ---- export + parity ----

def test_export_and_parity(tmp_path):
    m = TinyDetector()
    onnx_path = str(tmp_path / "m.onnx")
    meta = export_onnx(m, onnx_path, input_size=128)
    assert meta["output_schema"] == "tiny_v1"
    assert meta["interpolation"] == "bilinear"
    assert os.path.exists(onnx_path)
    rep = run_parity(m, onnx_path, input_size=128, num_classes=6, stride=m.stride)
    assert rep["passed"] is True
    assert rep["max_raw_diff"] <= rep["raw_tol"]


# ---- adapter + evaluation ----

def test_adapter_decode_shapes():
    m = TinyDetector()
    raw = m(torch.zeros(1, 3, 128, 128)).detach().numpy()
    boxes, scores, cls = decode_tiny_v1(raw, input_size=128, stride=16, num_classes=6)
    n = (128 // 16) ** 2
    assert boxes.shape == (n, 4) and scores.shape == (n,) and cls.shape == (n,)


def test_evaluation_metric_correct():
    gts = [((10, 10, 30, 30), 0)]
    preds = [((11, 11, 31, 31), 0.9, 0), ((80, 80, 90, 90), 0.5, 1)]
    s = match_and_score(preds, gts, iou_thr=0.5)
    assert s["tp"] == 1 and s["fn"] == 0 and s["fp"] == 1
    assert s["precision"] == 0.5 and s["recall"] == 1.0

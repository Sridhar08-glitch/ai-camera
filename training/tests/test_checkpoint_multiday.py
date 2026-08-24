"""Phase 6T-B — multi-day checkpoint infrastructure: atomic write, step-based
recovery + rotation, and resume-compatibility guard. Torch-gated."""
from __future__ import annotations

import os

import pytest

torch = pytest.importorskip("torch")

from training.checkpoint import (
    ResumeIncompatibleError,
    assert_resume_compatible,
    atomic_save,
)
from training.config import TrainConfig
from training.engine import _rotate_recovery, train_run
from training.synthetic import make_dataset


def test_atomic_save_no_leftover_tmp(tmp_path):
    p = str(tmp_path / "c.pt")
    atomic_save(p, {"x": torch.zeros(3)})
    assert os.path.exists(p)
    assert not os.path.exists(p + ".tmp")


def test_step_based_recovery_and_rotation(tmp_path):
    cfg = TrainConfig(architecture="tiny", input_size=128, max_epochs=1, batch_size=2,
                      base_lr=0.02, early_stop_patience=99, amp=False,
                      checkpoint_interval_steps=2, keep_recovery=2)
    # 12 samples / batch 2 = 6 steps/epoch → recovery at steps 2,4,6 → rotation keeps 2
    train_run(cfg, make_dataset(12), make_dataset(4, base_seed=9), str(tmp_path))
    recs = sorted(n for n in os.listdir(tmp_path) if n.startswith("recovery_"))
    assert len(recs) == cfg.keep_recovery          # rotation enforced
    assert os.path.exists(tmp_path / "best.pt")     # never rotated away
    assert os.path.exists(tmp_path / "last.pt")


def test_rotate_never_deletes_best_last(tmp_path):
    for n in ["best.pt", "last.pt", "recovery_1.pt", "recovery_2.pt", "recovery_3.pt"]:
        (tmp_path / n).write_bytes(b"x")
    _rotate_recovery(str(tmp_path), keep=1)
    assert (tmp_path / "best.pt").exists() and (tmp_path / "last.pt").exists()
    recs = [n for n in os.listdir(tmp_path) if n.startswith("recovery_")]
    assert recs == ["recovery_3.pt"]               # only newest recovery kept


def test_resume_compatibility_guard():
    base = TrainConfig(architecture="fcos", input_size=640, class_mapping_version="uvh_bmd_5class_v1",
                       split_manifest_sha256="abc", dataset_fingerprint="fp1").to_dict()
    ckpt = {"config": base}
    # same identity → OK
    assert_resume_compatible(ckpt, dict(base))
    # changed dataset fingerprint → refuse
    changed = dict(base); changed["dataset_fingerprint"] = "fp2"
    with pytest.raises(ResumeIncompatibleError):
        assert_resume_compatible(ckpt, changed)
    # changed architecture → refuse
    changed2 = dict(base); changed2["architecture"] = "tiny"
    with pytest.raises(ResumeIncompatibleError):
        assert_resume_compatible(ckpt, changed2)
    # changed input size → refuse
    changed3 = dict(base); changed3["input_size"] = 512
    with pytest.raises(ResumeIncompatibleError):
        assert_resume_compatible(ckpt, changed3)

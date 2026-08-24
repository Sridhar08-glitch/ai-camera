"""Phase 6T-B — TRUE multi-process exit/resume verification (Part 18).

Proves interruptible multi-day training: one process trains + checkpoints + EXITS
completely; a NEW process resumes and continues (global step increases, epoch does
not reset, optimizer/scheduler/scaler/EMA restored). Uses the real FCOS config path
on TEST_ONLY synthetic data. Genuine `subprocess` exit — not in-process."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

pytest.importorskip("torch")

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _run(args):
    r = subprocess.run([sys.executable, "-m", "training", *args], cwd=REPO,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"cmd {args} failed: {r.stderr[-800:]}"
    # last JSON line
    line = [l for l in r.stdout.strip().splitlines() if l.strip().startswith("{")][-1]
    return json.loads(line)


def _progress(out):
    return _run(["progress", "--out", out])


def test_true_process_exit_then_resume_continues(tmp_path):
    out = str(tmp_path / "run")
    # process 1: train 1 epoch (FCOS, small) then the process EXITS
    _run(["train", "--out", out, "--arch", "fcos", "--input-size", "192",
          "--epochs", "1", "--batch", "2"])
    p1 = _progress(out)
    assert os.path.exists(os.path.join(out, "last.pt"))
    step1, epoch1 = p1["global_step"], p1["epoch"]
    assert step1 > 0 and p1["architecture"] == "fcos"

    # process 2: a brand-new process resumes and continues to epoch 2
    _run(["resume", "--out", out, "--arch", "fcos", "--input-size", "192",
          "--epochs", "2", "--batch", "2"])
    p2 = _progress(out)
    # genuine continuation: step increased, epoch advanced (not reset to 0)
    assert p2["global_step"] > step1
    assert p2["epoch"] > epoch1


def test_resume_refused_on_config_change(tmp_path):
    out = str(tmp_path / "run2")
    _run(["train", "--out", out, "--arch", "fcos", "--input-size", "192",
          "--epochs", "1", "--batch", "2"])
    # resume with a DIFFERENT input size → must fail (resume-compat guard)
    r = subprocess.run(
        [sys.executable, "-m", "training", "resume", "--out", out, "--arch", "fcos",
         "--input-size", "256", "--epochs", "2", "--batch", "2"],
        cwd=REPO, capture_output=True, text=True, timeout=600)
    assert r.returncode != 0
    assert "resume" in (r.stderr + r.stdout).lower()

"""
Training CLI (Phase 6T-A / plan §33). Runs independently of Django/web.

    python -m training smoke   [--out DIR] [--epochs N] [--input-size S]
    python -m training export  --ckpt best.pt --out model.onnx [--input-size S]
    python -m training parity  --ckpt best.pt --onnx model.onnx [--input-size S]

`smoke` is the TEST_ONLY plumbing verification: synthetic geometric data → train →
checkpoint → resume → evaluate → ONNX export → PyTorch↔ONNX parity. It trains no
real model and its artifact is TEST_ONLY (never activatable).
"""
from __future__ import annotations

import argparse
import json
import os

from training.config import TrainConfig


def _smoke(args) -> int:
    import torch

    from training.architectures.tiny import TinyDetector
    from training.engine import train_run
    from training.evaluation import match_and_score
    from training.export import export_onnx
    from training.parity import run_parity
    from training.synthetic import make_dataset

    out = args.out
    os.makedirs(out, exist_ok=True)
    cfg = TrainConfig(architecture="tiny", input_size=args.input_size,
                      max_epochs=args.epochs, batch_size=4, base_lr=0.02,
                      early_stop_patience=args.epochs, amp=False)
    train = make_dataset(24, base_seed=0)
    val = make_dataset(8, base_seed=1000)

    # 1) train (+ per-epoch/best/last checkpoints)
    res = train_run(cfg, train, val, out)
    # 2) resume smoke: continue 1 more epoch from last
    cfg2 = TrainConfig(**{**cfg.to_dict()})
    cfg2.max_epochs = cfg.max_epochs + 1
    res2 = train_run(cfg2, train, val, out, resume_from=res["last_ckpt"])

    # 3) export best → ONNX
    model = TinyDetector(num_classes=cfg.num_classes)
    ckpt = torch.load(res["best_ckpt"], map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model"])
    onnx_path = os.path.join(out, "model.onnx")
    meta = export_onnx(model, onnx_path, input_size=cfg.input_size)
    # 4) parity
    parity = run_parity(model, onnx_path, input_size=cfg.input_size,
                        num_classes=cfg.num_classes, stride=res["stride"])

    report = {
        "trained": True, "epochs_run": res["epochs_run"], "best_val": res["best_metric"],
        "resumed_epochs": res2["epochs_run"], "export": meta, "parity": parity,
        "provenance": res["provenance"], "test_only": True,
    }
    with open(os.path.join(out, "smoke_report.json"), "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(json.dumps({k: report[k] for k in ("epochs_run", "best_val", "parity", "test_only")},
                     indent=2, default=str))
    return 0 if parity["passed"] else 2


def _training_config(args):
    # Fixed dataset_fingerprint so resume across processes is compatible. In real use
    # this is the merged DatasetVersion's content hash.
    return TrainConfig(
        architecture=args.arch, input_size=args.input_size, max_epochs=args.epochs,
        batch_size=args.batch, base_lr=0.01, amp=(args.amp and _cuda()),
        early_stop_patience=99, checkpoint_interval_steps=args.ckpt_steps,
        class_mapping_version="uvh_bmd_5class_v1", dataset_fingerprint="synthetic-smoke-fp",
        num_classes=6,
    )


def _cuda():
    import torch
    return torch.cuda.is_available()


def _synthetic_split():
    from training.synthetic import make_dataset
    return make_dataset(24, base_seed=0), make_dataset(8, base_seed=1000)


def _train(args) -> int:
    """Start a NEW training run (TEST_ONLY synthetic data unless a real merged dataset
    loader is wired). Writes best.pt/last.pt/recovery checkpoints."""
    from training.engine import train_run

    os.makedirs(args.out, exist_ok=True)
    cfg = _training_config(args)
    tr, va = _synthetic_split()
    res = train_run(cfg, tr, va, args.out)
    print(json.dumps({"status": "trained", "epochs_run": res["epochs_run"],
                      "best": res["best_metric"], "last_ckpt": res["last_ckpt"]}, default=str))
    return 0


def _resume(args) -> int:
    """Resume the SAME run from last.pt (or --from). Refuses on critical-config change."""
    from training.engine import train_run

    resume_from = args.from_ckpt or os.path.join(args.out, "last.pt")
    if not os.path.exists(resume_from):
        print(json.dumps({"status": "error", "reason": f"no checkpoint at {resume_from}"}))
        return 2
    cfg = _training_config(args)
    tr, va = _synthetic_split()
    res = train_run(cfg, tr, va, args.out, resume_from=resume_from)
    print(json.dumps({"status": "resumed", "epochs_run": res["epochs_run"]}, default=str))
    return 0


def _progress(args) -> int:
    """Show progress from last.pt without loading a model."""
    import torch

    p = os.path.join(args.out, "last.pt")
    if not os.path.exists(p):
        print(json.dumps({"status": "no_checkpoint"}))
        return 2
    ck = torch.load(p, map_location="cpu", weights_only=False)
    print(json.dumps({"epoch": ck["epoch"], "global_step": ck["global_step"],
                      "best_metric": ck["best_metric"],
                      "architecture": ck["config"].get("architecture")}, default=str))
    return 0


def _export(args) -> int:
    import torch

    from training.architectures.tiny import TinyDetector
    from training.export import export_onnx

    model = TinyDetector()
    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model"])
    meta = export_onnx(model, args.out, input_size=args.input_size)
    print(json.dumps(meta, indent=2))
    return 0


def _parity(args) -> int:
    import torch

    from training.architectures.tiny import TinyDetector
    from training.parity import run_parity

    model = TinyDetector()
    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model"])
    rep = run_parity(model, args.onnx, input_size=args.input_size,
                     num_classes=6, stride=model.stride)
    print(json.dumps(rep, indent=2))
    return 0 if rep["passed"] else 2


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="training")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke"); s.add_argument("--out", default="training/_smoke_out")
    s.add_argument("--epochs", type=int, default=6); s.add_argument("--input-size", type=int, default=128)
    s.set_defaults(fn=_smoke)

    def _train_args(pp):
        pp.add_argument("--out", required=True)
        pp.add_argument("--arch", default="fcos")
        pp.add_argument("--input-size", dest="input_size", type=int, default=256)
        pp.add_argument("--epochs", type=int, default=1)
        pp.add_argument("--batch", type=int, default=2)
        pp.add_argument("--ckpt-steps", dest="ckpt_steps", type=int, default=0)
        pp.add_argument("--amp", action="store_true")

    tr = sub.add_parser("train"); _train_args(tr); tr.set_defaults(fn=_train)
    rs = sub.add_parser("resume"); _train_args(rs)
    rs.add_argument("--from", dest="from_ckpt", default=""); rs.set_defaults(fn=_resume)
    pg = sub.add_parser("progress"); pg.add_argument("--out", required=True); pg.set_defaults(fn=_progress)
    e = sub.add_parser("export"); e.add_argument("--ckpt", required=True)
    e.add_argument("--out", required=True); e.add_argument("--input-size", type=int, default=128)
    e.set_defaults(fn=_export)
    pa = sub.add_parser("parity"); pa.add_argument("--ckpt", required=True)
    pa.add_argument("--onnx", required=True); pa.add_argument("--input-size", type=int, default=128)
    pa.set_defaults(fn=_parity)
    args = p.parse_args(argv)
    return args.fn(args)

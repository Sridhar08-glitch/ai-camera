"""
Checkpoint save/resume (Phase 6T-A / plan §32, ADR-036).

State dicts only (no pickled arbitrary objects). Preserves enough to resume an
interrupted run mid-training: model, optimizer, scheduler, AMP scaler, EMA, epoch,
global step, best metric, RNG state, and the config/provenance.
"""
from __future__ import annotations

import os

import torch


class ResumeIncompatibleError(RuntimeError):
    """Raised when a checkpoint's critical identity does not match the requested
    resume config (dataset/architecture/preprocessing change) — resume is refused
    rather than silently starting a corrupted continuation."""


# Fields that MUST match for a resume to be valid (Phase 6T-B / Part 15).
_CRITICAL = ("architecture", "num_classes", "input_size", "interpolation",
             "class_mapping_version", "split_manifest_sha256", "dataset_fingerprint")


def atomic_save(path: str, payload: dict) -> None:
    """Write to a temp file then os.replace → the previous valid checkpoint is never
    truncated if the process dies mid-write (Part 16 atomic checkpointing)."""
    tmp = f"{path}.tmp"
    torch.save(payload, tmp)
    os.replace(tmp, path)  # atomic on the same filesystem


def save_checkpoint(path: str, *, model, optimizer, scheduler, scaler, ema_state,
                    epoch: int, global_step: int, best_metric: float, config: dict,
                    provenance: dict) -> None:
    payload = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict() if scheduler is not None else None,
        "scaler": scaler.state_dict() if scaler is not None else None,
        "ema": ema_state,
        "epoch": epoch,
        "global_step": global_step,
        "best_metric": best_metric,
        "config": config,
        "provenance": provenance,
        "torch_rng_state": torch.get_rng_state(),
    }
    atomic_save(path, payload)


def assert_resume_compatible(ckpt: dict, config: dict) -> None:
    """Refuse resume if any critical identity field changed (Part 15)."""
    prev = ckpt.get("config", {}) or {}
    mismatched = []
    for f in _CRITICAL:
        if f in prev or f in config:
            if prev.get(f) != config.get(f):
                mismatched.append((f, prev.get(f), config.get(f)))
    if mismatched:
        details = "; ".join(f"{f}: {a!r}→{b!r}" for f, a, b in mismatched)
        raise ResumeIncompatibleError(
            f"cannot resume — critical inputs changed ({details}). Start a new run instead."
        )


def load_checkpoint(path: str, *, model, optimizer=None, scheduler=None, scaler=None,
                    map_location="cpu") -> dict:
    ckpt = torch.load(path, map_location=map_location, weights_only=False)
    model.load_state_dict(ckpt["model"])
    if optimizer is not None and ckpt.get("optimizer") is not None:
        optimizer.load_state_dict(ckpt["optimizer"])
    if scheduler is not None and ckpt.get("scheduler") is not None:
        scheduler.load_state_dict(ckpt["scheduler"])
    if scaler is not None and ckpt.get("scaler") is not None:
        scaler.load_state_dict(ckpt["scaler"])
    rng = ckpt.get("torch_rng_state")
    if rng is not None:
        # map_location may have moved the RNG ByteTensor to GPU; set_rng_state
        # requires a CPU ByteTensor.
        torch.set_rng_state(rng.cpu().to(torch.uint8))
    return ckpt

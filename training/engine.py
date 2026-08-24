"""
Training engine (Phase 6T-A / plan §14, §29, §32). Scratch training only.

Implements the TinyDetector training loop: dataset-scale-aware schedule (cosine +
warmup, max-epoch budget, early stopping), AMP (GPU only), EMA, gradient clipping,
per-epoch + best + last checkpoints, resume, and **NaN-loss handling** (abort + raise
rather than silently producing a bad model). No pretrained weights.

FCOS (torchvision) uses its own built-in loss dict; a thin branch is provided, but
the smoke/verification path uses TinyDetector for speed + determinism.
"""
from __future__ import annotations

import math
import os

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from training.checkpoint import (
    assert_resume_compatible,
    load_checkpoint,
    save_checkpoint,
)
from training.config import TrainConfig
from training.data import SyntheticDetectionDataset, build_targets, collate
from training.detector_adapter import get_training_adapter
from training.provenance import code_identity_hash, framework_versions


class NaNLossError(RuntimeError):
    pass


def _tiny_loss(raw, target, pos_mask, cls_idx, num_classes):
    """Standalone tiny-loss (kept for direct unit tests). The engine itself now uses
    the DetectorTrainingAdapter — this is not on the main path."""
    obj_loss = F.binary_cross_entropy_with_logits(raw[..., 4], target[..., 4])
    if pos_mask.any():
        pred_box = raw[..., 0:4][pos_mask]
        tgt_box = target[..., 0:4][pos_mask]
        box_loss = F.mse_loss(pred_box, tgt_box)
        cls_loss = F.cross_entropy(raw[..., 5:][pos_mask], cls_idx[pos_mask])
    else:
        box_loss = raw.sum() * 0.0
        cls_loss = raw.sum() * 0.0
    return obj_loss + box_loss + cls_loss


class _EMA:
    def __init__(self, model, decay=0.999):
        self.decay = decay
        self.shadow = {k: v.detach().clone() for k, v in model.state_dict().items()}

    def update(self, model):
        for k, v in model.state_dict().items():
            if v.dtype.is_floating_point:
                self.shadow[k].mul_(self.decay).add_(v.detach(), alpha=1 - self.decay)
            else:
                self.shadow[k] = v.detach().clone()

    def state(self):
        return {k: v.clone() for k, v in self.shadow.items()}


def train_run(config: TrainConfig, train_samples, val_samples, out_dir, *,
              resume_from=None, device=None, log=print):
    """Run a (scratch) training run. Returns a result dict. Deterministic for a seed."""
    os.makedirs(out_dir, exist_ok=True)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(config.seed)

    # Architecture-specific behavior is owned by the adapter; the loop below is
    # architecture-independent (Phase 6T-B).
    adapter = get_training_adapter(config.architecture)
    model = adapter.build_model(config.num_classes, config.input_size).to(device)
    stride = getattr(model, "stride", None)
    grid = model.grid_size(config.input_size) if hasattr(model, "grid_size") else None

    ds_tr = SyntheticDetectionDataset(train_samples, input_size=config.input_size)
    ds_va = SyntheticDetectionDataset(val_samples, input_size=config.input_size)
    dl_tr = DataLoader(ds_tr, batch_size=config.batch_size, shuffle=True, collate_fn=collate)
    dl_va = DataLoader(ds_va, batch_size=config.batch_size, shuffle=False, collate_fn=collate)

    opt = torch.optim.SGD(model.parameters(), lr=config.base_lr,
                          momentum=config.momentum, weight_decay=config.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, config.max_epochs))
    use_amp = config.amp and device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    ema = _EMA(model) if config.ema else None

    start_epoch, global_step, best = 0, 0, math.inf
    if resume_from and os.path.exists(resume_from):
        ckpt = load_checkpoint(resume_from, model=model, optimizer=opt, scheduler=sched,
                               scaler=scaler, map_location=device)
        # Refuse to resume if dataset/architecture/preprocessing identity changed.
        assert_resume_compatible(ckpt, config.to_dict())
        start_epoch = ckpt["epoch"] + 1
        global_step = ckpt["global_step"]
        best = ckpt.get("best_metric", math.inf)
        log(f"resumed from epoch {start_epoch} step {global_step}")

    provenance = {
        "code_identity": code_identity_hash(),
        "frameworks": framework_versions(),
        "config_hash": config.config_hash(),
    }
    history = []
    epochs_no_improve = 0
    last_ckpt = os.path.join(out_dir, "last.pt")
    best_ckpt = os.path.join(out_dir, "best.pt")

    for epoch in range(start_epoch, config.max_epochs):
        model.train()
        running = 0.0
        for imgs, boxes in dl_tr:
            imgs = imgs.to(device)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=use_amp):
                loss, loss_parts = adapter.compute_loss(model, imgs, boxes, device)
            if not torch.isfinite(loss):
                raise NaNLossError(
                    f"non-finite loss at epoch {epoch} step {global_step}: {loss_parts}")
            scaler.scale(loss).backward()
            if config.grad_clip:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip)
            scaler.step(opt)
            scaler.update()
            if ema:
                ema.update(model)
            running += float(loss.item())
            global_step += 1
            # Step-based recovery checkpoint (bounds unexpected lost work, Part 16).
            if config.checkpoint_interval_steps and global_step % config.checkpoint_interval_steps == 0:
                save_checkpoint(last_ckpt, model=model, optimizer=opt, scheduler=sched,
                                scaler=scaler, ema_state=(ema.state() if ema else None),
                                epoch=epoch, global_step=global_step, best_metric=best,
                                config=config.to_dict(), provenance=provenance)
                rec = os.path.join(out_dir, f"recovery_{global_step}.pt")
                save_checkpoint(rec, model=model, optimizer=opt, scheduler=sched,
                                scaler=scaler, ema_state=(ema.state() if ema else None),
                                epoch=epoch, global_step=global_step, best_metric=best,
                                config=config.to_dict(), provenance=provenance)
                _rotate_recovery(out_dir, config.keep_recovery)
        sched.step()
        train_loss = running / max(1, len(dl_tr))

        val_loss = _eval_loss(adapter, model, dl_va, device)
        history.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss})
        log(f"epoch {epoch}: train={train_loss:.4f} val={val_loss:.4f}")

        save_checkpoint(last_ckpt, model=model, optimizer=opt, scheduler=sched,
                        scaler=scaler, ema_state=(ema.state() if ema else None),
                        epoch=epoch, global_step=global_step, best_metric=best,
                        config=config.to_dict(), provenance=provenance)
        if val_loss < best - 1e-6:
            best = val_loss
            epochs_no_improve = 0
            save_checkpoint(best_ckpt, model=model, optimizer=opt, scheduler=sched,
                            scaler=scaler, ema_state=(ema.state() if ema else None),
                            epoch=epoch, global_step=global_step, best_metric=best,
                            config=config.to_dict(), provenance=provenance)
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= config.early_stop_patience:
                log(f"early stopping at epoch {epoch} (no improvement {epochs_no_improve})")
                break

    return {
        "best_metric": best, "epochs_run": len(history), "history": history,
        "best_ckpt": best_ckpt, "last_ckpt": last_ckpt, "provenance": provenance,
        "grid": grid, "stride": stride,
    }


def _rotate_recovery(out_dir, keep: int) -> None:
    """Keep only the newest `keep` recovery_<step>.pt files. NEVER touches best.pt /
    last.pt (Part 16: never auto-delete the best or latest valid checkpoint)."""
    recs = []
    for name in os.listdir(out_dir):
        if name.startswith("recovery_") and name.endswith(".pt"):
            try:
                recs.append((int(name[len("recovery_"):-3]), name))
            except ValueError:
                continue
    recs.sort()
    for _step, name in recs[:-keep] if keep > 0 else recs:
        try:
            os.remove(os.path.join(out_dir, name))
        except OSError:  # pragma: no cover - defensive
            pass


def _eval_loss(adapter, model, dl, device):
    """Validation-loss proxy via the adapter (train-mode loss under no_grad). For
    torchvision models this is a proxy — real model selection uses the mAP eval
    adapter (training.fcos_eval); sufficient here for early-stopping the smoke path."""
    total, n = 0.0, 0
    with torch.no_grad():
        for imgs, boxes in dl:
            imgs = imgs.to(device)
            loss, _ = adapter.compute_loss(model, imgs, boxes, device)
            total += float(loss.item())
            n += 1
    return total / max(1, n)

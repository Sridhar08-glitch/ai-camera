"""
Training recipe configuration (Phase 6T-A / plan §14, §29). Versioned + hashable.

Encodes the scratch-training recipe. The schedule is **dataset-scale-aware** with
early-stopping + a max budget (NOT a hard-coded 300-epoch plan). The whole config
is hashed into the training run's provenance so a recipe change is traceable.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass
class TrainConfig:
    # identity
    architecture: str = "tiny"                 # "tiny" | "fcos" | "yolox_s"
    num_classes: int = 6                       # canonical taxonomy v1
    input_size: int = 640
    interpolation: str = "bilinear"            # MUST match production preprocessing (ADR-037)
    pad_value: int = 114

    # optimization (scratch defaults; values needing experimentation flagged in docs)
    seed: int = 1234
    batch_size: int = 4
    grad_accum: int = 1
    base_lr: float = 0.01
    weight_decay: float = 5e-4
    momentum: float = 0.9
    warmup_iters: int = 50
    amp: bool = False                          # enable on GPU; CPU smoke runs fp32
    ema: bool = True
    grad_clip: float = 10.0

    # dataset-scale-aware schedule (not fixed 300 epochs)
    max_epochs: int = 50                       # hard cap (budget)
    early_stop_patience: int = 8               # stop if val metric plateaus
    aug_off_last_epochs: int = 5               # disable strong aug near the end
    eval_every: int = 1

    # multi-day interruptible training (Phase 6T-B): step-based recovery checkpoints
    # bound unexpected lost work; 0 → per-epoch only. `keep_recovery` rotates periodic
    # recovery checkpoints (best.pt + last.pt are never rotated away).
    checkpoint_interval_steps: int = 0
    keep_recovery: int = 3
    dataset_fingerprint: str = ""              # dataset identity for resume-compat guard

    # provenance (filled by the runner)
    dataset_version_ids: list = field(default_factory=list)
    split_manifest_sha256: str = ""
    taxonomy_version: str = "v1"
    class_mapping_version: str = "map-v1"

    def to_dict(self) -> dict:
        return asdict(self)

    def config_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

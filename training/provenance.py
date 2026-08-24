"""
Training reproducibility identity (Phase 6T-A / plan §31, ADR-036).

The repository is NOT a git repo, so a git SHA is unavailable. Reproducibility
therefore requires an explicit **code-identity hash**: a sha256 over the training
package's source files plus CODE_VERSION. No reproducibility claim is made without
it. This hash is recorded on every TrainingRun alongside dataset manifest hashes,
seed, taxonomy/mapping/preprocessing versions, and framework versions.
"""
from __future__ import annotations

import hashlib
import os

from training import CODE_VERSION

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def code_identity_hash() -> str:
    """Deterministic sha256 over all training/*.py sources + CODE_VERSION."""
    h = hashlib.sha256()
    h.update(CODE_VERSION.encode("utf-8"))
    for root, _dirs, files in os.walk(_PKG_DIR):
        if "__pycache__" in root or os.sep + "tests" in root or root.endswith("tests"):
            continue
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, _PKG_DIR).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            with open(path, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def framework_versions() -> dict:
    import numpy
    import torch

    info = {"torch": torch.__version__, "numpy": numpy.__version__,
            "torch_cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available()}
    try:
        import torchvision
        info["torchvision"] = torchvision.__version__
    except Exception:
        info["torchvision"] = None
    return info

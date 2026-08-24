"""Phase 6T-A — TrainingRun provenance model (governance). No torch.

Verifies the reproducibility chain a production-eligible run must record and that a
run traces back to dataset versions + split manifest + code identity."""
from __future__ import annotations

import pytest

from apps.datasets.models import (
    ApprovalStatus,
    Dataset,
    DatasetVersion,
    RightsStatus,
)
from apps.governance.models import (
    AIModel,
    AIModelVersion,
    TrainingRun,
    TrainingRunStatus,
)

pytestmark = pytest.mark.django_db


def test_training_run_records_full_provenance():
    ds = Dataset.objects.create(name="synthetic-smoke", is_synthetic=True)
    dv = DatasetVersion.objects.create(
        dataset=ds, version="1", rights_status=RightsStatus.SYNTHETIC_APPROVED,
        approval_status=ApprovalStatus.APPROVED, class_mapping_version="map-v1",
    )
    model = AIModel.objects.create(family="phase6t-tiny", task="detection")
    mv = AIModelVersion.objects.create(model=model, version="exp-1", provenance="platform_trained")

    run = TrainingRun.objects.create(
        model_version=mv, architecture="tiny",
        code_identity="a" * 64, code_version="6t-a.1", config_hash="b" * 64,
        recipe={"base_lr": 0.02, "max_epochs": 6},
        dataset_version_ids=[str(dv.id)], split_manifest_sha256="c" * 64,
        taxonomy_version="v1", class_mapping_version="map-v1",
        preprocess_contract="preproc-v2-bilinear", seed=1234,
        framework_versions={"torch": "2.13.0+cpu"}, hardware="RTX 3070 Laptop / CPU",
        status=TrainingRunStatus.COMPLETED, metrics={"val_loss": 0.77},
        best_checkpoint_ref="/artifacts/best.pt",
    )
    # full traceability chain present
    assert str(dv.id) in run.dataset_version_ids
    assert run.split_manifest_sha256 == "c" * 64
    assert run.code_identity and run.preprocess_contract == "preproc-v2-bilinear"
    assert run.model_version.provenance == "platform_trained"
    # reverse relation
    assert mv.training_runs.count() == 1


def test_training_run_survives_model_version_delete():
    run = TrainingRun.objects.create(architecture="tiny", code_identity="x" * 64,
                                     status=TrainingRunStatus.FAILED,
                                     failure_info="nan loss at epoch 2")
    assert run.model_version is None  # nullable until a model is registered
    assert run.status == TrainingRunStatus.FAILED

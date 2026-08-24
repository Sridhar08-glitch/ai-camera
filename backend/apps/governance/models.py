"""
Model & algorithm governance (Phase 2 §15–17 / ADR-015).

Metadata + provenance + artifact references only. No weights in PostgreSQL, no
inference, no downloads. Deterministic algorithms are governed separately from AI
models so they are not misrepresented as ML.
"""
from __future__ import annotations

from django.db import models

from apps.common.datacategories import DataCategory
from apps.common.models import UUIDModel, UUIDTimeStampedModel


class ModelTask(models.TextChoices):
    DETECTION = "detection", "Object detection"
    TRACKING = "tracking", "Object tracking"
    PREDICTION = "prediction", "Traffic prediction"
    ANOMALY = "anomaly", "Anomaly detection"
    OTHER = "other", "Other"


class Provenance(models.TextChoices):
    PRETRAINED = "pretrained", "Third-party pretrained"
    FINETUNED = "finetuned", "Fine-tuned"
    PLATFORM_TRAINED = "platform_trained", "Trained by this platform"
    IMPORTED = "imported", "Imported custom model"
    TRADITIONAL_ML = "traditional_ml", "Traditional ML"


class ModelLifecycle(models.TextChoices):
    """Promotion lifecycle (Phase 6 / §30). Only APPROVED may be activated; a
    TEST_ONLY version (deterministic/project test artifact) can NEVER be activated
    for production."""
    DRAFT = "draft", "Draft"
    TRAINING = "training", "Training"
    EVALUATED = "evaluated", "Evaluated"
    CANDIDATE = "candidate", "Candidate"
    APPROVED = "approved", "Approved"
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retired"
    TEST_ONLY = "test_only", "Test-only (never production)"


class AIModel(UUIDTimeStampedModel):
    family = models.CharField(max_length=128)
    task = models.CharField(max_length=32, choices=ModelTask.choices)
    provider = models.CharField(max_length=128, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "governance_ai_model"
        ordering = ["family", "task"]
        constraints = [
            models.UniqueConstraint(
                fields=["family", "task", "provider"], name="uq_aimodel_family_task_provider"
            )
        ]

    def __str__(self) -> str:
        return f"{self.family} [{self.task}]"


class AIModelVersion(UUIDModel):
    model = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=64)
    provenance = models.CharField(max_length=32, choices=Provenance.choices)
    license = models.CharField(max_length=128, blank=True, default="")
    source_url = models.CharField(max_length=512, blank=True, default="")
    config = models.JSONField(default=dict, blank=True)
    input_spec = models.JSONField(default=dict, blank=True)
    output_schema_version = models.CharField(max_length=32, blank=True, default="")
    class_map = models.JSONField(default=dict, blank=True)
    benchmark_summary = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16, choices=ModelLifecycle.choices, default=ModelLifecycle.DRAFT
    )
    is_active = models.BooleanField(default=False)  # currently-loaded flag (status must be ACTIVE)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_ai_model_version"
        ordering = ["model", "version"]
        constraints = [
            models.UniqueConstraint(fields=["model", "version"], name="uq_aimodelversion_model_version")
        ]

    def __str__(self) -> str:
        return f"{self.model.family}:{self.version}"


class ArtifactKind(models.TextChoices):
    WEIGHTS = "weights", "Weights"
    CONFIG = "config", "Config"
    LABELS = "labels", "Labels"


class ModelArtifact(UUIDModel):
    model_version = models.ForeignKey(
        AIModelVersion, on_delete=models.CASCADE, related_name="artifacts"
    )
    kind = models.CharField(max_length=16, choices=ArtifactKind.choices)
    path = models.CharField(max_length=512)  # reference only — no blob in DB
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    size_bytes = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_model_artifact"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.kind}:{self.path}"


class ModelEvaluation(UUIDModel):
    model_version = models.ForeignKey(
        AIModelVersion, on_delete=models.CASCADE, related_name="evaluations"
    )
    dataset_ref = models.CharField(max_length=256, blank=True, default="")
    metrics = models.JSONField(default=dict, blank=True)
    provenance_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_model_evaluation"
        ordering = ["-created_at"]


class TrainingRunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    INTERRUPTED = "interrupted", "Interrupted"


class TrainingRun(UUIDModel):
    """Full provenance of a training run (Phase 6T-A / plan §30, §31, ADR-036).

    Answers "which code/architecture/datasets/samples/split/taxonomy/augmentations/
    seed/hyperparameters/framework/hardware/artifact produced this model version".
    Large checkpoints are NOT stored here — only references (via StoredArtifact/paths).
    `model_version` is null until a resulting model is registered. Written by the
    isolated training runtime through a governed registration step (Django never
    trains)."""

    model_version = models.ForeignKey(
        AIModelVersion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="training_runs",
    )
    architecture = models.CharField(max_length=64)
    code_identity = models.CharField(max_length=64)          # sha256 over training code
    code_version = models.CharField(max_length=32, blank=True, default="")
    config_hash = models.CharField(max_length=64, blank=True, default="")
    recipe = models.JSONField(default=dict, blank=True)       # bounded recipe summary
    dataset_version_ids = models.JSONField(default=list, blank=True)
    split_manifest_sha256 = models.CharField(max_length=64, blank=True, default="")
    taxonomy_version = models.CharField(max_length=16, blank=True, default="")
    class_mapping_version = models.CharField(max_length=32, blank=True, default="")
    preprocess_contract = models.CharField(max_length=32, blank=True, default="")
    seed = models.BigIntegerField(null=True, blank=True)
    framework_versions = models.JSONField(default=dict, blank=True)
    hardware = models.CharField(max_length=256, blank=True, default="")
    status = models.CharField(
        max_length=16, choices=TrainingRunStatus.choices, default=TrainingRunStatus.QUEUED
    )
    metrics = models.JSONField(default=dict, blank=True)
    best_checkpoint_ref = models.CharField(max_length=1024, blank=True, default="")
    exported_artifact_ref = models.CharField(max_length=1024, blank=True, default="")
    failure_info = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_training_run"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["architecture", "status"])]

    def __str__(self) -> str:
        return f"trainrun {self.architecture} [{self.status}] {str(self.id)[:8]}"


class AlgorithmDefinition(UUIDTimeStampedModel):
    key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    category = models.CharField(max_length=64, blank=True, default="")
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "governance_algorithm_definition"
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class AlgorithmVersion(UUIDModel):
    definition = models.ForeignKey(
        AlgorithmDefinition, on_delete=models.CASCADE, related_name="versions"
    )
    version = models.CharField(max_length=64)
    config = models.JSONField(default=dict, blank=True)
    config_hash = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_algorithm_version"
        ordering = ["definition", "version"]
        constraints = [
            models.UniqueConstraint(fields=["definition", "version"], name="uq_algoversion_def_version")
        ]

    def save(self, *args, **kwargs):
        # Versions are immutable after creation (reproducibility).
        if not self._state.adding:
            raise ValueError("AlgorithmVersion is immutable once created.")
        return super().save(*args, **kwargs)


class ArtifactState(models.TextChoices):
    PRESENT = "present", "Present"
    ORPHANED = "orphaned", "Orphaned"
    DELETED = "deleted", "Deleted"


class StoredArtifact(UUIDModel):
    """Reusable file registry (Phase 2 §20). Authoritative for physical-file facts.

    Phase 4 adds a lifecycle `state` for orphan reconciliation (ADR-022). Still no
    storage engine here — file bytes live behind a StorageBackend keyed by `path`.
    """

    category = models.CharField(max_length=32, choices=DataCategory.choices)
    path = models.CharField(max_length=512)  # = storage key
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    size_bytes = models.BigIntegerField(null=True, blank=True)
    state = models.CharField(max_length=16, choices=ArtifactState.choices, default=ArtifactState.PRESENT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "governance_stored_artifact"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["category", "state"]), models.Index(fields=["checksum_sha256"])]

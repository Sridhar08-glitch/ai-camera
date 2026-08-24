"""
Dataset governance + rights + provenance (Phase 6T-A / ADR-029, ADR-035).

Metadata + rights evidence + immutable manifest references only. **No media blobs
in PostgreSQL** — images/videos and manifest files live behind a StorageBackend /
StoredArtifact keyed by reference; the DB holds identity, rights status, hashes,
counts, and split-manifest references.

The production-training eligibility gate (`gate.py`) reads `DatasetVersion.rights_status`;
only the eligible statuses may feed a production-eligible training run. This is
enforced in the training runtime/CLI, not merely in the UI.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDModel, UUIDTimeStampedModel
from apps.processing.taxonomy import TAXONOMY_VERSION


class RightsStatus(models.TextChoices):
    """Production-training eligibility (Phase 6T-A / plan §12).

    Eligible (production training may use): APPROVED_COMMERCIAL, APPROVED_WITH_OBLIGATIONS,
    INTERNAL_AUTHORIZED, SYNTHETIC_APPROVED. Everything else is rejected for production
    training (RESEARCH_ONLY may be used only in explicitly-flagged throwaway experiments
    that can never register a production model)."""

    APPROVED_COMMERCIAL = "approved_commercial", "Approved — commercial"
    APPROVED_WITH_OBLIGATIONS = "approved_with_obligations", "Approved — with obligations"
    INTERNAL_AUTHORIZED = "internal_authorized", "Internal / authorized own data"
    SYNTHETIC_APPROVED = "synthetic_approved", "Synthetic — approved"
    RESEARCH_ONLY = "research_only", "Research only"
    LICENSE_UNCLEAR = "license_unclear", "License unclear"
    REJECTED = "rejected", "Rejected"


# The only statuses from which a DatasetVersion may feed PRODUCTION-eligible training.
PRODUCTION_ELIGIBLE_STATUSES = frozenset({
    RightsStatus.APPROVED_COMMERCIAL,
    RightsStatus.APPROVED_WITH_OBLIGATIONS,
    RightsStatus.INTERNAL_AUTHORIZED,
    RightsStatus.SYNTHETIC_APPROVED,
})


class ApprovalStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Dataset(UUIDTimeStampedModel):
    """A dataset identity (real or synthetic). Not a version — versions carry rights."""

    name = models.CharField(max_length=200, unique=True)
    publisher = models.CharField(max_length=200, blank=True, default="")
    official_source_url = models.CharField(max_length=1024, blank=True, default="")
    is_synthetic = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "datasets_dataset"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DatasetLicense(UUIDModel):
    """Rights evidence for a dataset (primary-source-backed). Immutable record of
    what was verified, by whom, and when — separates verified fact from interpretation."""

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="licenses")
    license_identifier = models.CharField(max_length=128)          # e.g. "CC BY 4.0", "CC BY-NC-SA 4.0"
    license_url = models.CharField(max_length=1024, blank=True, default="")
    primary_source_url = models.CharField(max_length=1024, blank=True, default="")
    evidence = models.TextField(blank=True, default="")            # quoted primary text / notes
    commercial_use = models.BooleanField(default=False)
    training_use = models.BooleanField(default=False)              # ML-training explicitly addressed
    attribution_required = models.BooleanField(default=False)
    redistribution_restrictions = models.TextField(blank=True, default="")
    verified = models.BooleanField(default=False)                 # primary source actually verified
    verified_by = models.CharField(max_length=200, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "datasets_license"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.dataset_id}:{self.license_identifier}"


class DatasetVersion(UUIDModel):
    """A specific, rights-classified version of a dataset. Carries the eligibility
    status the training gate reads, the canonical taxonomy/mapping versions, and
    references (never blobs) to the dataset root + immutable manifest."""

    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="versions")
    version = models.CharField(max_length=64)
    license = models.ForeignKey(
        DatasetLicense, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    rights_status = models.CharField(
        max_length=32, choices=RightsStatus.choices, default=RightsStatus.LICENSE_UNCLEAR
    )
    approval_status = models.CharField(
        max_length=16, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT
    )
    approved_by = models.CharField(max_length=200, blank=True, default="")
    taxonomy_version = models.CharField(max_length=16, default=TAXONOMY_VERSION)
    class_mapping_version = models.CharField(max_length=32, blank=True, default="")
    dataset_root = models.CharField(max_length=1024, blank=True, default="")  # reference only
    manifest = models.ForeignKey(
        "DatasetManifest", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    imported_sample_count = models.PositiveIntegerField(default=0)
    annotation_count = models.PositiveIntegerField(default=0)
    obligations = models.TextField(blank=True, default="")        # e.g. attribution text
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "datasets_version"
        ordering = ["dataset", "version"]
        constraints = [
            models.UniqueConstraint(fields=["dataset", "version"], name="uq_datasetversion_dataset_version")
        ]

    def __str__(self) -> str:
        return f"{self.dataset_id}:{self.version} [{self.rights_status}]"

    @property
    def is_production_eligible(self) -> bool:
        """True only if rights AND approval both permit production training."""
        return (
            self.rights_status in PRODUCTION_ELIGIBLE_STATUSES
            and self.approval_status == ApprovalStatus.APPROVED
        )


class DatasetImport(UUIDModel):
    """One import run for a DatasetVersion: what was ingested + validation outcome.
    Idempotent — the same source + config reproduces the same manifest hash."""

    dataset_version = models.ForeignKey(
        DatasetVersion, on_delete=models.CASCADE, related_name="imports"
    )
    source_reference = models.CharField(max_length=1024, blank=True, default="")
    parser = models.CharField(max_length=128, blank=True, default="")
    mapping_version = models.CharField(max_length=32, blank=True, default="")
    scanned_count = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    validation_report = models.JSONField(default=dict, blank=True)
    dedup_report = models.JSONField(default=dict, blank=True)
    outcome = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "datasets_import"
        ordering = ["-created_at"]


class ManifestKind(models.TextChoices):
    SAMPLES = "samples", "Sample manifest"
    SPLIT = "split", "Split manifest"


class DatasetManifest(UUIDModel):
    """Immutable, content-hashed manifest reference (Phase 6T-A / ADR-035).

    The per-sample rows live in a manifest *file* (behind storage) whose sha256 is
    recorded here — the DB never stores the (potentially millions of) rows. The hash
    is the tamper-evidence + reproducibility anchor. Immutable after creation."""

    dataset_version = models.ForeignKey(
        DatasetVersion, on_delete=models.CASCADE, related_name="manifests"
    )
    kind = models.CharField(max_length=16, choices=ManifestKind.choices)
    content_sha256 = models.CharField(max_length=64, db_index=True)
    sample_count = models.PositiveIntegerField(default=0)
    storage_ref = models.CharField(max_length=1024, blank=True, default="")  # file reference
    # Split-specific reproducibility metadata (null for sample manifests).
    split_seed = models.BigIntegerField(null=True, blank=True)
    grouping_strategy = models.CharField(max_length=32, blank=True, default="")
    split_counts = models.JSONField(default=dict, blank=True)  # {train:n, val:n, test:n}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "datasets_manifest"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["dataset_version", "kind"])]

    def save(self, *args, **kwargs):
        # Immutable after creation (reproducibility + tamper-evidence).
        if not self._state.adding:
            raise ValueError("DatasetManifest is immutable once created.")
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.kind}:{self.content_sha256[:12]} n={self.sample_count}"

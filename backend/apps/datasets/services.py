"""
Dataset import orchestration (Phase 6T-A). Ties conversion → validation → dedup →
leakage-safe split → immutable manifests → governance rows into one idempotent run.
Pure-Python/Django (no torch). Media stays on disk/behind storage; DB holds
references + hashes + counts only.
"""
from __future__ import annotations

import os

from django.db import transaction

from apps.datasets.coco import to_canonical_coco
from apps.datasets.dedup import dedup_report
from apps.datasets.manifests import SampleRecord, write_manifest
from apps.datasets.models import (
    Dataset,
    DatasetImport,
    DatasetManifest,
    DatasetVersion,
    ManifestKind,
    RightsStatus,
)
from apps.datasets.splits import assign_splits, check_no_leakage, split_counts
from apps.datasets.validation import validate_coco


def build_dataset_version_from_coco(
    *,
    dataset_name: str,
    version: str,
    rights_status: str,
    is_synthetic: bool,
    images: list,
    raw_annotations: list,
    samples: list,            # list[SampleRecord] (media_checksum + group_key + source)
    mapping_version: str,
    source_format: str,
    timestamp: str,
    out_dir: str,
    seed: int = 1234,
    ratios: tuple = (0.8, 0.1, 0.1),
    grouping_strategy: str = "group_key",
) -> DatasetVersion:
    """Run the full import pipeline and persist governance rows + manifest files.

    Returns the created DatasetVersion (approval_status=DRAFT — approval is a
    separate governed decision; the training gate still requires APPROVED)."""
    os.makedirs(out_dir, exist_ok=True)

    # 1) canonical COCO conversion (+ provenance).
    coco_doc, conv_report = to_canonical_coco(
        images=images, raw_annotations=raw_annotations, mapping_version=mapping_version,
        source_format=source_format, timestamp=timestamp,
    )
    # 2) validation.
    val_report = validate_coco(coco_doc)
    # 3) exact dedup.
    dd = dedup_report([(s.sample_id, s.media_checksum) for s in samples])
    # 4) leakage-safe split.
    split_records = assign_splits(samples, seed=seed, ratios=ratios,
                                  grouping_strategy=grouping_strategy)
    leakage = check_no_leakage(split_records)
    if leakage:
        raise ValueError(f"leakage detected in split: {leakage[:3]}")
    counts = split_counts(split_records)

    meta = {
        "taxonomy_version": coco_doc["info"]["taxonomy_version"],
        "class_mapping_version": mapping_version,
        "seed": seed, "grouping_strategy": grouping_strategy, "ratios": list(ratios),
    }
    samples_path = os.path.join(out_dir, "samples_manifest.json")
    split_path = os.path.join(out_dir, "split_manifest.json")
    samples_sha = write_manifest(samples_path, samples, meta=meta)
    split_sha = write_manifest(split_path, split_records, meta=meta)

    with transaction.atomic():
        ds, _ = Dataset.objects.get_or_create(
            name=dataset_name, defaults={"is_synthetic": is_synthetic}
        )
        dv = DatasetVersion.objects.create(
            dataset=ds, version=version, rights_status=rights_status,
            class_mapping_version=mapping_version, dataset_root=out_dir,
            imported_sample_count=len(samples),
            annotation_count=len(coco_doc["annotations"]),
        )
        DatasetManifest.objects.create(
            dataset_version=dv, kind=ManifestKind.SAMPLES,
            content_sha256=samples_sha, sample_count=len(samples), storage_ref=samples_path,
        )
        split_manifest = DatasetManifest.objects.create(
            dataset_version=dv, kind=ManifestKind.SPLIT, content_sha256=split_sha,
            sample_count=len(split_records), storage_ref=split_path,
            split_seed=seed, grouping_strategy=grouping_strategy, split_counts=counts,
        )
        dv.manifest = split_manifest
        dv.save(update_fields=["manifest"])
        DatasetImport.objects.create(
            dataset_version=dv, source_reference=out_dir, parser=source_format,
            mapping_version=mapping_version, scanned_count=len(samples),
            imported_count=len(samples), rejected_count=dd["duplicate_groups"],
            validation_report=val_report, dedup_report=dd, outcome="ok",
        )
    return dv

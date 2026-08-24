"""Phase 6T-A — end-to-end dataset import service (convert→validate→dedup→split→
manifests→governance rows). No torch."""
from __future__ import annotations

import pytest

from apps.datasets.manifests import SampleRecord, verify_manifest_file
from apps.datasets.models import DatasetManifest, DatasetVersion, ManifestKind, RightsStatus
from apps.datasets.services import build_dataset_version_from_coco

pytestmark = pytest.mark.django_db


def _fixture(n_groups=6, per_group=4):
    images, raw, samples = [], [], []
    iid = 1
    for g in range(n_groups):
        for i in range(per_group):
            images.append({"id": iid, "file_name": f"g{g}_{i}.jpg",
                           "width": 640, "height": 480, "group_key": f"vid{g}"})
            raw.append({"image_id": iid, "source_label": "car", "bbox": [10, 10, 40, 30]})
            samples.append(SampleRecord(sample_id=f"g{g}_{i}", media_checksum=f"c{g}_{i}",
                                        group_key=f"vid{g}", source="synthetic", class_ids=[0]))
            iid += 1
    return images, raw, samples


def test_import_service_creates_version_and_manifests(tmp_path):
    images, raw, samples = _fixture()
    dv = build_dataset_version_from_coco(
        dataset_name="synthetic-smoke", version="1",
        rights_status=RightsStatus.SYNTHETIC_APPROVED, is_synthetic=True,
        images=images, raw_annotations=raw, samples=samples,
        mapping_version="map-v1", source_format="synthetic",
        timestamp="2026-07-16T00:00:00Z", out_dir=str(tmp_path / "ds"),
        seed=99, ratios=(0.5, 0.25, 0.25),
    )
    assert isinstance(dv, DatasetVersion)
    assert dv.imported_sample_count == len(samples)
    assert dv.annotation_count == len(raw)

    manifests = DatasetManifest.objects.filter(dataset_version=dv)
    assert manifests.count() == 2
    split = manifests.get(kind=ManifestKind.SPLIT)
    assert sum(split.split_counts.values()) == len(samples)
    # split manifest file integrity verifies against its recorded hash
    assert verify_manifest_file(split.storage_ref, split.content_sha256) is True
    # version is DRAFT (not yet approved) → NOT production-eligible until approved
    assert dv.is_production_eligible is False


def test_import_is_deterministic(tmp_path):
    images, raw, samples = _fixture()
    dv1 = build_dataset_version_from_coco(
        dataset_name="d1", version="1", rights_status=RightsStatus.SYNTHETIC_APPROVED,
        is_synthetic=True, images=images, raw_annotations=raw, samples=samples,
        mapping_version="map-v1", source_format="synthetic",
        timestamp="2026-07-16T00:00:00Z", out_dir=str(tmp_path / "a"), seed=5,
    )
    dv2 = build_dataset_version_from_coco(
        dataset_name="d2", version="1", rights_status=RightsStatus.SYNTHETIC_APPROVED,
        is_synthetic=True, images=images, raw_annotations=raw, samples=samples,
        mapping_version="map-v1", source_format="synthetic",
        timestamp="2026-07-16T00:00:00Z", out_dir=str(tmp_path / "b"), seed=5,
    )
    s1 = DatasetManifest.objects.get(dataset_version=dv1, kind=ManifestKind.SPLIT)
    s2 = DatasetManifest.objects.get(dataset_version=dv2, kind=ManifestKind.SPLIT)
    assert s1.content_sha256 == s2.content_sha256  # deterministic split → identical hash

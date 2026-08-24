"""Phase 6T-A — dataset governance, rights gate, manifests, provenance (no torch)."""
from __future__ import annotations

import os
import tempfile

import pytest

from apps.datasets.gate import (
    DatasetGateError,
    assert_versions_eligible,
    check_version_eligible,
)
from apps.datasets.manifests import (
    SampleRecord,
    manifest_sha256,
    verify_manifest_file,
    write_manifest,
)
from apps.datasets.models import (
    ApprovalStatus,
    Dataset,
    DatasetManifest,
    DatasetVersion,
    ManifestKind,
    RightsStatus,
)

pytestmark = pytest.mark.django_db


def _version(rights, approval=ApprovalStatus.APPROVED, name="d"):
    ds = Dataset.objects.create(name=name)
    return DatasetVersion.objects.create(
        dataset=ds, version="1", rights_status=rights, approval_status=approval
    )


# ---- production gate ----

@pytest.mark.parametrize("rights", [
    RightsStatus.SYNTHETIC_APPROVED, RightsStatus.INTERNAL_AUTHORIZED,
    RightsStatus.APPROVED_COMMERCIAL, RightsStatus.APPROVED_WITH_OBLIGATIONS,
])
def test_gate_accepts_eligible(rights):
    v = _version(rights, name=f"ok-{rights}")
    assert check_version_eligible(v).eligible is True
    assert_versions_eligible([v])  # no raise


@pytest.mark.parametrize("rights", [
    RightsStatus.RESEARCH_ONLY, RightsStatus.LICENSE_UNCLEAR, RightsStatus.REJECTED,
])
def test_gate_rejects_ineligible_rights(rights):
    v = _version(rights, name=f"bad-{rights}")
    assert check_version_eligible(v).eligible is False
    with pytest.raises(DatasetGateError) as exc:
        assert_versions_eligible([v])
    assert exc.value.code == "not_eligible"


def test_gate_rejects_unapproved_even_if_rights_ok():
    v = _version(RightsStatus.SYNTHETIC_APPROVED, approval=ApprovalStatus.DRAFT)
    assert check_version_eligible(v).eligible is False
    with pytest.raises(DatasetGateError):
        assert_versions_eligible([v])


def test_gate_empty_rejected():
    with pytest.raises(DatasetGateError) as exc:
        assert_versions_eligible([])
    assert exc.value.code == "no_datasets"


def test_research_only_flag_allows_only_research_experiments():
    v = _version(RightsStatus.RESEARCH_ONLY)
    # allowed for a flagged throwaway experiment...
    assert_versions_eligible([v], allow_research_only=True)
    # ...but LICENSE_UNCLEAR is still rejected even with the flag
    bad = _version(RightsStatus.LICENSE_UNCLEAR, name="unclear")
    with pytest.raises(DatasetGateError):
        assert_versions_eligible([bad], allow_research_only=True)


# ---- manifests: determinism, immutability, tamper detection ----

def _records():
    return [
        SampleRecord(sample_id="b", media_checksum="h2", group_key="vid2", class_ids=[0]),
        SampleRecord(sample_id="a", media_checksum="h1", group_key="vid1", class_ids=[1]),
    ]


def test_manifest_hash_deterministic_and_order_independent():
    r1 = _records()
    r2 = list(reversed(_records()))
    assert manifest_sha256(r1) == manifest_sha256(r2)  # sorted internally


def test_manifest_hash_changes_with_meta():
    r = _records()
    assert manifest_sha256(r, meta={"seed": 1}) != manifest_sha256(r, meta={"seed": 2})


def test_manifest_write_and_verify_tamper():
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "m.json")
    digest = write_manifest(path, _records(), meta={"seed": 7})
    assert verify_manifest_file(path, digest) is True
    # tamper: append a byte → verification fails
    with open(path, "ab") as fh:
        fh.write(b" ")
    assert verify_manifest_file(path, digest) is False


def test_datasetmanifest_row_is_immutable():
    v = _version(RightsStatus.SYNTHETIC_APPROVED)
    m = DatasetManifest.objects.create(
        dataset_version=v, kind=ManifestKind.SAMPLES,
        content_sha256="a" * 64, sample_count=3,
    )
    m.sample_count = 4
    with pytest.raises(ValueError):
        m.save()


def test_is_production_eligible_property():
    v = _version(RightsStatus.SYNTHETIC_APPROVED)
    assert v.is_production_eligible is True
    v2 = _version(RightsStatus.RESEARCH_ONLY, name="r")
    assert v2.is_production_eligible is False

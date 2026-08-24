"""Phase 6T-B — Gate D: Open Images metadata candidate pipeline + explicit human
approval gate. Metadata-only (no image download); approval is explicit + audited."""
from __future__ import annotations

import pytest

from apps.audit.models import AuditEvent, EventType
from apps.datasets.approval import (
    ApprovalError,
    approve_dataset_version,
    reject_dataset_version,
)
from apps.datasets.models import (
    ApprovalStatus,
    Dataset,
    DatasetVersion,
    RightsStatus,
)
from apps.datasets.openimages import select_candidates

pytestmark = pytest.mark.django_db

CC_BY = "https://creativecommons.org/licenses/by/2.0/"
CC_BY_NC = "https://creativecommons.org/licenses/by-nc/2.0/"


def _img(iid, license="", author="a", landing="http://src/x"):
    return {"image_id": iid, "license": license, "author": author,
            "original_landing_url": landing, "original_url": "", "title": "t"}


def test_openimages_candidate_selection_metadata_only():
    image_meta = [
        _img("i1", CC_BY),                       # permissive + vehicle → candidate
        _img("i2", CC_BY_NC),                    # non-commercial → excluded
        _img("i3", ""),                          # missing license → excluded
        _img("i4", CC_BY, author=""),            # missing rights metadata → excluded
        _img("i5", CC_BY),                       # no vehicle boxes → excluded
    ]
    box_rows = [
        {"image_id": "i1", "label": "Car"}, {"image_id": "i1", "label": "Bus"},
        {"image_id": "i2", "label": "Car"}, {"image_id": "i3", "label": "Truck"},
        {"image_id": "i4", "label": "Car"},
        {"image_id": "i5", "label": "Dog"},      # not a vehicle
    ]
    out = select_candidates(image_meta, box_rows)
    assert out["candidate_count"] == 1
    c = out["candidates"][0]
    assert c["image_id"] == "i1" and c["approval"] == "PENDING_HUMAN_LEGAL_REVIEW"
    assert set(c["classes"]) == {"Car", "Bus"}
    assert out["rights_status"] == "LICENSE_UNCLEAR"     # NOT production-eligible
    assert out["excluded"]["non_permissive_license"] == 1
    assert out["excluded"]["missing_license"] == 1
    assert out["excluded"]["missing_rights_metadata"] == 1
    assert out["excluded"]["no_vehicle_boxes"] == 1
    assert out["class_counts"]["Car"] == 1 and out["class_counts"]["Bus"] == 1


def test_candidates_are_never_auto_eligible():
    # A version created from candidates defaults to LICENSE_UNCLEAR/DRAFT → blocked.
    ds = Dataset.objects.create(name="openimages-candidates")
    v = DatasetVersion.objects.create(dataset=ds, version="cand-1",
                                      rights_status=RightsStatus.LICENSE_UNCLEAR)
    assert v.is_production_eligible is False


def test_explicit_approval_is_audited_and_gates_training():
    ds = Dataset.objects.create(name="own-footage")
    v = DatasetVersion.objects.create(dataset=ds, version="1",
                                      rights_status=RightsStatus.LICENSE_UNCLEAR)
    assert v.is_production_eligible is False

    approve_dataset_version(v, rights_status=RightsStatus.INTERNAL_AUTHORIZED,
                            approver="legal@holora", obligations="internal use only")
    v.refresh_from_db()
    assert v.rights_status == RightsStatus.INTERNAL_AUTHORIZED
    assert v.approval_status == ApprovalStatus.APPROVED
    assert v.is_production_eligible is True
    assert AuditEvent.objects.filter(event_type=EventType.DATASET_VERSION_APPROVED).count() == 1


def test_approval_requires_approver_and_eligible_status():
    ds = Dataset.objects.create(name="d")
    v = DatasetVersion.objects.create(dataset=ds, version="1")
    with pytest.raises(ApprovalError) as e1:
        approve_dataset_version(v, rights_status=RightsStatus.SYNTHETIC_APPROVED, approver="")
    assert e1.value.code == "no_approver"
    # cannot "approve" to a non-eligible status
    with pytest.raises(ApprovalError) as e2:
        approve_dataset_version(v, rights_status=RightsStatus.RESEARCH_ONLY, approver="x")
    assert e2.value.code == "not_eligible_status"


def test_reject_is_audited():
    ds = Dataset.objects.create(name="d2")
    v = DatasetVersion.objects.create(dataset=ds, version="1",
                                      rights_status=RightsStatus.LICENSE_UNCLEAR)
    reject_dataset_version(v, approver="legal@holora", reason="license unclear")
    v.refresh_from_db()
    assert v.rights_status == RightsStatus.REJECTED
    assert v.is_production_eligible is False
    assert AuditEvent.objects.filter(event_type=EventType.DATASET_VERSION_REJECTED).count() == 1

"""
Dataset approval — an EXPLICIT, AUDITED human gate (Phase 6T-B / Part Q).

Software collects evidence, enforces status, and prevents unauthorized training — but
the decision to make a DatasetVersion production-eligible is a deliberate human action,
never automatic. This service performs that action and records an audit event. It is
invoked explicitly (management command / authorized API), never as a side effect of
import or candidate selection.
"""
from __future__ import annotations

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.datasets.models import ApprovalStatus, DatasetVersion, RightsStatus


class ApprovalError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


def approve_dataset_version(
    version: DatasetVersion,
    *,
    rights_status: str,
    approver: str,
    obligations: str = "",
    request=None,
) -> DatasetVersion:
    """Explicitly approve a DatasetVersion to a production-eligible rights status.

    Requires a non-empty approver. Records `DATASET_VERSION_APPROVED`. Raises if the
    target rights_status is not a production-eligible one (use `reject_dataset_version`
    for the rest)."""
    from apps.datasets.models import PRODUCTION_ELIGIBLE_STATUSES

    if not approver:
        raise ApprovalError("no_approver", "an explicit approver identity is required")
    if rights_status not in {s.value for s in PRODUCTION_ELIGIBLE_STATUSES}:
        raise ApprovalError(
            "not_eligible_status",
            f"{rights_status} is not a production-eligible status; approval refused",
        )
    version.rights_status = rights_status
    version.approval_status = ApprovalStatus.APPROVED
    version.approved_by = approver
    if obligations:
        version.obligations = obligations
    version.save(update_fields=["rights_status", "approval_status", "approved_by", "obligations"])
    record_audit(
        EventType.DATASET_VERSION_APPROVED, action="approve_dataset_version",
        request=request, target_type="DatasetVersion", target_id=version.id,
        metadata={"rights_status": rights_status, "approver": approver,
                  "dataset": version.dataset.name, "version": version.version},
    )
    return version


def reject_dataset_version(version: DatasetVersion, *, approver: str, reason: str = "",
                           request=None) -> DatasetVersion:
    version.rights_status = RightsStatus.REJECTED
    version.approval_status = ApprovalStatus.REJECTED
    version.approved_by = approver
    version.save(update_fields=["rights_status", "approval_status", "approved_by"])
    record_audit(
        EventType.DATASET_VERSION_REJECTED, action="reject_dataset_version",
        request=request, target_type="DatasetVersion", target_id=version.id,
        metadata={"approver": approver, "reason": reason[:200],
                  "dataset": version.dataset.name, "version": version.version},
    )
    return version

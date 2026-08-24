"""
Production-training eligibility gate (Phase 6T-A / plan §12). CODE-enforced.

This is the single authoritative check the training runtime/CLI calls before any
production-eligible training run. It rejects any DatasetVersion that is not both
rights-eligible AND approved. Frontend validation is never sufficient on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.datasets.models import (
    PRODUCTION_ELIGIBLE_STATUSES,
    ApprovalStatus,
    DatasetVersion,
    RightsStatus,
)


class DatasetGateError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list[str]


def check_version_eligible(version: DatasetVersion) -> EligibilityResult:
    """Return eligibility + human-readable reasons for one DatasetVersion."""
    reasons: list[str] = []
    if version.rights_status not in PRODUCTION_ELIGIBLE_STATUSES:
        reasons.append(
            f"rights_status={version.rights_status} is not production-eligible "
            f"(need one of {sorted(s.value for s in PRODUCTION_ELIGIBLE_STATUSES)})"
        )
    if version.approval_status != ApprovalStatus.APPROVED:
        reasons.append(f"approval_status={version.approval_status} (must be APPROVED)")
    return EligibilityResult(eligible=not reasons, reasons=reasons)


def assert_versions_eligible(versions, *, allow_research_only: bool = False) -> None:
    """Hard gate: raise DatasetGateError unless EVERY version is production-eligible.

    `allow_research_only=True` is ONLY for explicitly-flagged throwaway experiments
    (never a production model); it permits RESEARCH_ONLY but still rejects
    LICENSE_UNCLEAR / REJECTED and anything unapproved."""
    if not versions:
        raise DatasetGateError("no_datasets", "no dataset versions supplied for training")
    for v in versions:
        if allow_research_only and v.rights_status == RightsStatus.RESEARCH_ONLY:
            continue
        result = check_version_eligible(v)
        if not result.eligible:
            raise DatasetGateError(
                "not_eligible",
                f"dataset version {v.dataset_id}:{v.version} rejected: {'; '.join(result.reasons)}",
            )


def eligible_version_ids(queryset=None) -> list:
    """Convenience: ids of all production-eligible DatasetVersions."""
    qs = queryset if queryset is not None else DatasetVersion.objects.all()
    return [v.id for v in qs if check_version_eligible(v).eligible]

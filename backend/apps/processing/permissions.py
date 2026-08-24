"""
Processing permissions (Phase 5 §31). Server-side enforced.

Admins + operator control processing; analyst reads completed sessions; viewer and
incident_operator are excluded from raw-video processing resources (privacy, §32).
"""
from __future__ import annotations

from apps.common.permissions import HasAnyRole
from apps.common.roles import RoleCode

_CONTROL_ROLES = frozenset({
    RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN, RoleCode.TRAFFIC_OPERATOR,
})
_READ_ROLES = _CONTROL_ROLES | {RoleCode.TRAFFIC_ANALYST}


class CanControlProcessing(HasAnyRole):
    """Create / cancel / stop / pause / resume / retry."""

    allowed_roles = _CONTROL_ROLES


class CanReadProcessing(HasAnyRole):
    allowed_roles = _READ_ROLES

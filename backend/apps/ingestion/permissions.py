"""Video permissions (Phase 4 §14). Viewer is excluded from all video access (privacy)."""
from __future__ import annotations

from apps.common.permissions import HasAnyRole
from apps.common.roles import RoleCode

_READ_ROLES = frozenset({
    RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN, RoleCode.TRAFFIC_OPERATOR,
    RoleCode.TRAFFIC_ANALYST, RoleCode.INCIDENT_OPERATOR,
})  # viewer intentionally excluded
_UPLOAD_ROLES = frozenset({RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN, RoleCode.TRAFFIC_OPERATOR})
_MANAGE_ROLES = frozenset({RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN})


class CanReadVideo(HasAnyRole):
    allowed_roles = _READ_ROLES


class CanUploadVideo(HasAnyRole):
    allowed_roles = _UPLOAD_ROLES


class CanManageVideo(HasAnyRole):
    allowed_roles = _MANAGE_ROLES  # archive + download original

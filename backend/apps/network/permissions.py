"""Network permissions (Phase 3 §22). Read: any authenticated. Write: admin roles."""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.common.roles import ADMIN_ROLES


def _role(user):
    return getattr(getattr(user, "role", None), "code", None)


class NetworkReadOrAdminWrite(BasePermission):
    """All authenticated users may read; only system_admin/traffic_admin may write."""

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return _role(user) in ADMIN_ROLES

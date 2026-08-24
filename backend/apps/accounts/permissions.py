"""Object-level permission helpers for user management."""
from __future__ import annotations

from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.common.roles import ADMIN_ROLES, RoleCode


class IsSelfOrAdmin(BasePermission):
    """
    Admins (system/traffic) may act on any user. A non-admin may only read or
    update their own record (and cannot change role/active — enforced in the
    serializer). Only System Admin may delete or assign roles (checked in view).
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        code = getattr(getattr(user, "role", None), "code", None)
        if code in ADMIN_ROLES:
            return True
        # Non-admins: only themselves, and not delete.
        if request.method == "DELETE":
            return False
        if request.method in SAFE_METHODS or request.method in ("PUT", "PATCH"):
            return obj.id == user.id
        return False


def can_manage_target_role(actor_role: str | None, target_role: str | None) -> bool:
    """
    Traffic Admin may not create/edit users with an admin role; only System
    Admin may. System Admin may manage any role.
    """
    if actor_role == RoleCode.SYSTEM_ADMIN:
        return True
    if actor_role == RoleCode.TRAFFIC_ADMIN:
        return target_role not in ADMIN_ROLES
    return False

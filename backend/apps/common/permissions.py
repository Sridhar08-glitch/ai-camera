"""
Role-based DRF permission classes (Phase 1 §10/§11).

Authorization is enforced server-side. Frontend gating is cosmetic only.
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.common.roles import ADMIN_ROLES, RoleCode


def _role_code(user) -> str | None:
    role = getattr(user, "role", None)
    return getattr(role, "code", None) if role else None


class HasAnyRole(BasePermission):
    """Base class: subclass and set `allowed_roles`."""

    allowed_roles: frozenset[str] = frozenset()

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return _role_code(user) in self.allowed_roles


class IsSystemAdmin(HasAnyRole):
    allowed_roles = frozenset({RoleCode.SYSTEM_ADMIN})


class IsAdminRole(HasAnyRole):
    """System Administrator or Traffic Administrator."""

    allowed_roles = ADMIN_ROLES

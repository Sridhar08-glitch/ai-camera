"""
Canonical role vocabulary (Phase 0 §32 / Phase 1 §11).

Defined in `common` so it is a foundational concept the whole platform shares,
without any app-specific dependency.
"""
from __future__ import annotations

from django.db import models


class RoleCode(models.TextChoices):
    SYSTEM_ADMIN = "system_admin", "System Administrator"
    TRAFFIC_ADMIN = "traffic_admin", "Traffic Administrator"
    TRAFFIC_OPERATOR = "traffic_operator", "Traffic Operator"
    TRAFFIC_ANALYST = "traffic_analyst", "Traffic Analyst"
    INCIDENT_OPERATOR = "incident_operator", "Incident Operator"
    VIEWER = "viewer", "Viewer"


# Roles allowed to administer users (create/list). Only SYSTEM_ADMIN may delete
# users or assign roles; TRAFFIC_ADMIN may manage non-admin users only.
ADMIN_ROLES = frozenset({RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN})

# Role definitions seeded at migration time.
ROLE_DEFINITIONS: dict[str, str] = {
    RoleCode.SYSTEM_ADMIN: "Full control including user and role management.",
    RoleCode.TRAFFIC_ADMIN: "Manage traffic configuration and non-admin users.",
    RoleCode.TRAFFIC_OPERATOR: "Operate monitoring and processing sessions.",
    RoleCode.TRAFFIC_ANALYST: "Read analytics and reports.",
    RoleCode.INCIDENT_OPERATOR: "Manage alerts and incident candidates.",
    RoleCode.VIEWER: "Read-only access.",
}

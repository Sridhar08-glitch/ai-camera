"""Permission-matrix tests (Phase 1 §11). Server-side enforcement."""
from __future__ import annotations

import pytest

from apps.common.roles import RoleCode

pytestmark = pytest.mark.django_db

ADMIN = {RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN}
ALL_ROLES = list(RoleCode.values)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_user_list_admin_only(api, auth, make_user, role):
    auth(api, make_user(role, email=f"list-{role}@ex.com"))
    resp = api.get("/api/v1/users")
    if role in ADMIN:
        assert resp.status_code == 200
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_user_create_admin_only(api, auth, make_user, role):
    auth(api, make_user(role, email=f"create-{role}@ex.com"))
    resp = api.post(
        "/api/v1/users",
        {"email": f"x-{role}@ex.com", "full_name": "X", "role": "viewer", "password": "TrafficPass123!"},
    )
    if role in ADMIN:
        assert resp.status_code == 201
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_delete_system_admin_only(api, auth, make_user, role):
    actor = make_user(role, email=f"del-actor-{role}@ex.com")
    target = make_user(RoleCode.VIEWER, email=f"del-target-{role}@ex.com")
    auth(api, actor)
    resp = api.delete(f"/api/v1/users/{target.id}")
    if role == RoleCode.SYSTEM_ADMIN:
        assert resp.status_code == 204
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_assign_role_system_admin_only(api, auth, make_user, role):
    actor = make_user(role, email=f"assign-actor-{role}@ex.com")
    target = make_user(RoleCode.VIEWER, email=f"assign-target-{role}@ex.com")
    auth(api, actor)
    resp = api.post(f"/api/v1/users/{target.id}/role", {"role": "viewer"})
    if role == RoleCode.SYSTEM_ADMIN:
        assert resp.status_code == 200
    else:
        assert resp.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_me_all_roles(api, auth, make_user, role):
    auth(api, make_user(role, email=f"me-{role}@ex.com"))
    assert api.get("/api/v1/auth/me").status_code == 200


def test_non_admin_cannot_read_other_user(api, auth, make_user, viewer):
    other = make_user(RoleCode.TRAFFIC_ANALYST, email="other@ex.com")
    auth(api, viewer)
    assert api.get(f"/api/v1/users/{other.id}").status_code == 403

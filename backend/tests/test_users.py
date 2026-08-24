"""API tests for user management + roles + pagination."""
from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.common.roles import RoleCode
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_roles_list_any_authenticated(api, auth, viewer):
    auth(api, viewer)
    resp = api.get("/api/v1/roles")
    assert resp.status_code == 200
    codes = {r["code"] for r in resp.json()["data"]}
    assert set(RoleCode.values) == codes


def test_admin_creates_user(api, auth, sysadmin):
    auth(api, sysadmin)
    resp = api.post(
        "/api/v1/users",
        {"email": "new@example.com", "full_name": "New", "role": "viewer", "password": PASSWORD},
    )
    assert resp.status_code == 201
    assert User.objects.filter(email="new@example.com").exists()


def test_create_user_weak_password_rejected(api, auth, sysadmin):
    auth(api, sysadmin)
    resp = api.post(
        "/api/v1/users",
        {"email": "weak@example.com", "full_name": "W", "role": "viewer", "password": "123"},
    )
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_traffic_admin_cannot_create_system_admin(api, auth, traffic_admin):
    auth(api, traffic_admin)
    resp = api.post(
        "/api/v1/users",
        {"email": "sa@example.com", "full_name": "SA", "role": "system_admin", "password": PASSWORD},
    )
    assert resp.status_code == 400  # role validation rejects


def test_user_list_paginated(api, auth, sysadmin, make_user):
    for i in range(3):
        make_user(RoleCode.VIEWER, email=f"v{i}@example.com")
    auth(api, sysadmin)
    resp = api.get("/api/v1/users?page_size=2")
    body = resp.json()
    assert resp.status_code == 200
    assert "meta" in body and body["meta"]["pagination"]["page_size"] == 2
    assert len(body["data"]) == 2


def test_self_edit_full_name(api, auth, viewer):
    auth(api, viewer)
    resp = api.patch(f"/api/v1/users/{viewer.id}", {"full_name": "Renamed"})
    assert resp.status_code == 200
    viewer.refresh_from_db()
    assert viewer.full_name == "Renamed"


def test_self_cannot_change_own_role(api, auth, viewer):
    auth(api, viewer)
    resp = api.patch(f"/api/v1/users/{viewer.id}", {"role": "system_admin"})
    assert resp.status_code == 400


def test_sysadmin_assigns_role(api, auth, sysadmin, viewer):
    auth(api, sysadmin)
    resp = api.post(f"/api/v1/users/{viewer.id}/role", {"role": "traffic_analyst"})
    assert resp.status_code == 200
    viewer.refresh_from_db()
    assert viewer.role.code == "traffic_analyst"


def test_sysadmin_deletes_user(api, auth, sysadmin, viewer):
    auth(api, sysadmin)
    resp = api.delete(f"/api/v1/users/{viewer.id}")
    assert resp.status_code == 204
    assert not User.objects.filter(id=viewer.id).exists()


def test_sysadmin_cannot_delete_self(api, auth, sysadmin):
    auth(api, sysadmin)
    resp = api.delete(f"/api/v1/users/{sysadmin.id}")
    assert resp.status_code == 400

"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, User
from apps.common.roles import RoleCode

PASSWORD = "TrafficPass123!"


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def roles(db) -> dict[str, Role]:
    return {r.code: r for r in Role.objects.all()}


@pytest.fixture
def make_user(db, roles):
    def _make(role_code: str, email: str | None = None, **extra) -> User:
        email = email or f"{role_code}@example.com"
        return User.objects.create_user(
            email=email,
            password=PASSWORD,
            role=roles[role_code],
            **extra,
        )

    return _make


@pytest.fixture
def sysadmin(make_user) -> User:
    return make_user(RoleCode.SYSTEM_ADMIN)


@pytest.fixture
def traffic_admin(make_user) -> User:
    return make_user(RoleCode.TRAFFIC_ADMIN)


@pytest.fixture
def operator(make_user) -> User:
    return make_user(RoleCode.TRAFFIC_OPERATOR)


@pytest.fixture
def viewer(make_user) -> User:
    return make_user(RoleCode.VIEWER)


@pytest.fixture
def auth():
    """Return a helper that authenticates an APIClient as a user via real JWT."""

    def _auth(client: APIClient, user: User) -> APIClient:
        token = RefreshToken.for_user(user).access_token
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _auth


@pytest.fixture
def vstorage(settings, tmp_path):
    """Isolate Phase 4 video storage under a temp dir and reset the backend singleton."""
    settings.VIDEO_STORAGE_ROOT = str(tmp_path / "videos")
    settings.VIDEO_TEMP_ROOT = str(tmp_path / "tmp")
    import apps.ingestion.storage as st

    st._backend = None
    yield tmp_path
    st._backend = None

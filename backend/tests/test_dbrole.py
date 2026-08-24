"""Verify the application runs under the least-privilege role (ADR-014)."""
from __future__ import annotations

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def _role_attrs():
    with connection.cursor() as cur:
        cur.execute(
            "SELECT current_user, "
            "(SELECT rolsuper FROM pg_roles WHERE rolname=current_user), "
            "(SELECT rolcreaterole FROM pg_roles WHERE rolname=current_user), "
            "(SELECT rolcreatedb FROM pg_roles WHERE rolname=current_user)"
        )
        return cur.fetchone()


def test_runtime_role_is_aitraffic_app():
    user, *_ = _role_attrs()
    assert user == "aitraffic_app"


def test_runtime_role_is_not_superuser():
    _, rolsuper, _, _ = _role_attrs()
    assert rolsuper is False


def test_runtime_role_cannot_create_roles():
    _, _, rolcreaterole, _ = _role_attrs()
    assert rolcreaterole is False


def test_runtime_role_has_createdb_for_local_tests():
    # Development-only convenience so pytest can create test databases (ADR-014).
    _, _, _, rolcreatedb = _role_attrs()
    assert rolcreatedb is True

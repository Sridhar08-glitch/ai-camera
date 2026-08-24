"""API + failure tests for authentication and token security."""
from __future__ import annotations

import pytest
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db

COOKIE = settings.REFRESH_COOKIE["NAME"]


def test_login_success_sets_httponly_cookie_not_body(api, viewer):
    resp = api.post("/api/v1/auth/login", {"email": viewer.email, "password": PASSWORD})
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "access" in body
    assert "refresh" not in body  # refresh must NOT be in the body (clarification #1)
    assert COOKIE in resp.cookies
    cookie = resp.cookies[COOKIE]
    assert cookie["httponly"] is True
    assert cookie["path"] == "/api/v1/auth"


def test_login_invalid_password_401_envelope(api, viewer):
    resp = api.post("/api/v1/auth/login", {"email": viewer.email, "password": "wrong-pass-99"})
    assert resp.status_code == 400 or resp.status_code == 401
    assert "error" in resp.json()


def test_me_requires_auth(api):
    assert api.get("/api/v1/auth/me").status_code == 401


def test_me_returns_identity(api, auth, operator):
    auth(api, operator)
    data = api.get("/api/v1/auth/me").json()["data"]
    assert data["email"] == operator.email
    assert data["role"] == "traffic_operator"
    assert "permissions" in data


def test_refresh_rotates_from_cookie(api, viewer):
    login = api.post("/api/v1/auth/login", {"email": viewer.email, "password": PASSWORD})
    api.cookies[COOKIE] = login.cookies[COOKIE].value
    resp = api.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert "access" in resp.json()["data"]
    assert COOKIE in resp.cookies  # rotated


def test_refresh_without_cookie_401(api):
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_logout_blacklists_refresh(api, viewer):
    login = api.post("/api/v1/auth/login", {"email": viewer.email, "password": PASSWORD})
    refresh_value = login.cookies[COOKIE].value
    # authenticate with access for the logout call
    access = RefreshToken(refresh_value).access_token
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    api.cookies[COOKIE] = refresh_value
    resp = api.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    # the blacklisted refresh can no longer be used
    api.cookies[COOKIE] = refresh_value
    api.credentials()
    assert api.post("/api/v1/auth/refresh").status_code == 401


def test_invalid_access_token_rejected(api):
    api.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert api.get("/api/v1/auth/me").status_code == 401

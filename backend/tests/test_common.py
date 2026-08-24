"""Unit tests for common foundations."""
from __future__ import annotations

import uuid

import pytest

from apps.common.request_context import get_request_id, set_request_id
from apps.common.responses import EnvelopeJSONRenderer, data_envelope
from apps.common.roles import ADMIN_ROLES, ROLE_DEFINITIONS, RoleCode


def test_role_vocabulary_complete():
    assert set(ROLE_DEFINITIONS) == set(RoleCode.values)
    assert RoleCode.SYSTEM_ADMIN in ADMIN_ROLES
    assert RoleCode.TRAFFIC_ADMIN in ADMIN_ROLES
    assert RoleCode.VIEWER not in ADMIN_ROLES


def test_data_envelope_shape():
    assert data_envelope([1, 2]) == {"data": [1, 2]}
    assert data_envelope({"a": 1}, meta={"m": 2}) == {"data": {"a": 1}, "meta": {"m": 2}}


def test_envelope_renderer_wraps_plain_payload():
    out = EnvelopeJSONRenderer().render({"email": "x@y.z"})
    assert b'"data"' in out


def test_envelope_renderer_leaves_error_untouched():
    out = EnvelopeJSONRenderer().render({"error": {"code": "x"}})
    assert b'"error"' in out and b'"data"' not in out


def test_request_id_contextvar():
    set_request_id("abc123")
    assert get_request_id() == "abc123"


@pytest.mark.django_db
def test_uuid_pk_on_user(make_user):
    user = make_user(RoleCode.VIEWER)
    assert isinstance(user.id, uuid.UUID)
    assert user.created_at is not None

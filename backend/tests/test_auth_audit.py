"""Authentication actions emit the correct audit events (Phase 2 §5)."""
from __future__ import annotations

import pytest

from apps.audit.models import AuditEvent, EventType
from tests.conftest import PASSWORD

pytestmark = pytest.mark.django_db


def _events(event_type):
    return AuditEvent.objects.filter(event_type=event_type)


def test_login_success_audited(api, viewer, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        api.post("/api/v1/auth/login", {"email": viewer.email, "password": PASSWORD})
    ev = _events(EventType.LOGIN_SUCCESS).first()
    assert ev is not None
    assert ev.actor_id == viewer.id
    assert ev.request_id  # correlation preserved


def test_login_failure_audited_without_password(api, viewer, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        api.post("/api/v1/auth/login", {"email": viewer.email, "password": "wrong-pass-1"})
    ev = _events(EventType.LOGIN_FAILURE).first()
    assert ev is not None
    assert "wrong-pass-1" not in str(ev.metadata)
    assert ev.metadata.get("email") == viewer.email


def test_logout_audited(api, auth, operator, django_capture_on_commit_callbacks):
    auth(api, operator)
    with django_capture_on_commit_callbacks(execute=True):
        api.post("/api/v1/auth/logout")
    assert _events(EventType.LOGOUT).filter(actor_id=operator.id).exists()


def test_user_creation_audited(api, auth, sysadmin):
    auth(api, sysadmin)
    api.post("/api/v1/users", {"email": "n@ex.com", "full_name": "N", "role": "viewer", "password": PASSWORD})
    assert _events(EventType.USER_CREATED).filter(metadata__email="n@ex.com").exists()


def test_role_change_audited(api, auth, sysadmin, viewer):
    auth(api, sysadmin)
    api.post(f"/api/v1/users/{viewer.id}/role", {"role": "traffic_analyst"})
    ev = _events(EventType.ROLE_CHANGED).filter(target_id=str(viewer.id)).first()
    assert ev is not None
    assert ev.metadata["to"] == "traffic_analyst"


def test_deactivation_audited(api, auth, sysadmin, viewer):
    auth(api, sysadmin)
    api.patch(f"/api/v1/users/{viewer.id}", {"is_active": False})
    assert _events(EventType.USER_DEACTIVATED).filter(target_id=str(viewer.id)).exists()

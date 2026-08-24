"""Audit foundation tests: creation, immutability, sanitization, permissions."""
from __future__ import annotations

import pytest
from django.db import connection, transaction

from apps.audit.models import AuditEvent, AuditImmutableError, EventType, Outcome
from apps.audit.services import record_audit, sanitize_metadata

pytestmark = pytest.mark.django_db


# --- creation & context --------------------------------------------------

def test_record_audit_creates_event(sysadmin):
    ev = record_audit(
        EventType.USER_CREATED, action="create_user", actor=sysadmin,
        target_type="User", target_id="abc", metadata={"email": "x@y.z"},
    )
    assert ev.pk is not None
    assert ev.event_type == EventType.USER_CREATED
    assert ev.actor_id == sysadmin.id
    assert ev.actor_email == sysadmin.email
    assert ev.actor_role == "system_admin"


def test_sanitizer_strips_secrets():
    dirty = {
        "password": "hunter2", "access_token": "jwt.abc", "Authorization": "Bearer x",
        "cookie": "sid=1", "refresh": "r.tok", "email": "x@y.z", "nested": {"api_key": "k"},
    }
    clean = sanitize_metadata(dirty)
    assert clean["password"] == "[redacted]"
    assert clean["access_token"] == "[redacted]"
    assert clean["Authorization"] == "[redacted]"
    assert clean["cookie"] == "[redacted]"
    assert clean["refresh"] == "[redacted]"
    assert clean["nested"]["api_key"] == "[redacted]"
    assert clean["email"] == "x@y.z"


def test_recorded_metadata_never_contains_secrets():
    ev = record_audit(
        EventType.LOGIN_FAILURE, action="login", outcome=Outcome.FAILURE,
        metadata={"password": "secret", "token": "t", "email": "a@b.c"},
    )
    ev.refresh_from_db()
    assert "secret" not in str(ev.metadata)
    assert ev.metadata["password"] == "[redacted]"
    assert ev.metadata["email"] == "a@b.c"


# --- immutability (required attempts) ------------------------------------

def _make_event() -> AuditEvent:
    return record_audit(EventType.LOGOUT, action="logout")


def test_instance_update_rejected():
    ev = _make_event()
    ev.action = "tampered"
    with pytest.raises(AuditImmutableError):
        ev.save()


def test_instance_delete_rejected():
    ev = _make_event()
    with pytest.raises(AuditImmutableError):
        ev.delete()


def test_queryset_update_rejected():
    _make_event()
    with pytest.raises(AuditImmutableError):
        AuditEvent.objects.all().update(action="tampered")


def test_queryset_delete_rejected():
    _make_event()
    with pytest.raises(AuditImmutableError):
        AuditEvent.objects.all().delete()


def test_database_trigger_blocks_raw_update():
    ev = _make_event()
    with pytest.raises(Exception) as exc:  # DB trigger raises
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE audit_event SET action='x' WHERE id=%s", [str(ev.id)])
    assert "immutable" in str(exc.value).lower()


# --- actor deletion preserves the record ---------------------------------

def test_actor_deletion_preserves_immutable_record(make_user):
    """Actor is referenced by value (no FK): deleting the user must NOT modify the
    audit row (the immutability trigger would block any UPDATE), and the actor
    identity is preserved via id + snapshot."""
    from apps.accounts.models import User
    from apps.common.roles import RoleCode

    user = make_user(RoleCode.VIEWER, email="temp@ex.com")
    ev = record_audit(EventType.LOGIN_SUCCESS, action="login", actor=user)
    uid = user.id
    user.delete()  # must not raise, must not touch audit_event
    ev.refresh_from_db()
    assert ev.actor_id == uid          # preserved (no SET NULL)
    assert ev.actor_email == "temp@ex.com"  # snapshot retained
    assert not User.objects.filter(id=uid).exists()


# --- API permissions ------------------------------------------------------

def test_audit_list_requires_system_admin(api, auth, traffic_admin):
    auth(api, traffic_admin)
    assert api.get("/api/v1/audit/events").status_code == 403


def test_audit_list_allows_system_admin(api, auth, sysadmin):
    record_audit(EventType.LOGOUT, action="logout")
    auth(api, sysadmin)
    resp = api.get("/api/v1/audit/events")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


def test_audit_api_has_no_write_routes(api, auth, sysadmin):
    ev = record_audit(EventType.LOGOUT, action="logout")
    auth(api, sysadmin)
    # No update/delete verbs exposed.
    assert api.delete(f"/api/v1/audit/events/{ev.id}").status_code in (403, 405)
    assert api.patch(f"/api/v1/audit/events/{ev.id}", {"action": "x"}).status_code in (403, 405)


# --- emission modes -------------------------------------------------------

def test_best_effort_swallows_errors(monkeypatch):
    from apps.audit import services

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(services.AuditEvent.objects, "create", boom)
    # best_effort must not raise
    assert services.record_audit(EventType.LOGOUT, action="logout", best_effort=True) is None


def test_transactional_propagates_error(monkeypatch):
    from apps.audit import services

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(services.AuditEvent.objects, "create", boom)
    with pytest.raises(RuntimeError):
        services.record_audit(EventType.USER_CREATED, action="create_user")

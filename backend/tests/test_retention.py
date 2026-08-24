"""Retention framework tests: dry-run, bounded delete, idempotency, safety, audit."""
from __future__ import annotations

import pytest
from freezegun import freeze_time

from apps.audit.models import AuditEvent, EventType
from apps.common.datacategories import DataCategory
from apps.retention.models import RetentionPolicy, RetentionRun, RunOutcome
from apps.retention.registry import get_handler, registered_categories
from apps.retention.services import execute_policy

pytestmark = pytest.mark.django_db


def _old_audit_events(n: int):
    with freeze_time("2020-01-01"):
        for _ in range(n):
            AuditEvent.objects.create(event_type=EventType.LOGOUT, action="logout")


def _audit_policy(**over) -> RetentionPolicy:
    p = RetentionPolicy.objects.get(category=DataCategory.SECURITY_AUDIT)
    p.enabled = True
    p.retention_days = 365
    for k, v in over.items():
        setattr(p, k, v)
    p.save()
    return p


def test_policies_seeded():
    cats = set(RetentionPolicy.objects.values_list("category", flat=True))
    assert DataCategory.SECURITY_AUDIT in cats
    assert DataCategory.SYSTEM_METRIC in cats


def test_handlers_registered_only_for_existing_data():
    cats = set(registered_categories())
    assert DataCategory.SECURITY_AUDIT in cats
    assert DataCategory.SYSTEM_METRIC in cats
    # RAW_VIDEO/VIDEO_THUMBNAIL gained handlers in Phase 4 (data now exists).
    # A category with no data yet still has no handler (skipped safely).
    assert get_handler(DataCategory.SIMULATION_ARTIFACT) is None


def test_dry_run_scans_without_deleting():
    _old_audit_events(5)
    policy = _audit_policy()
    run = execute_policy(policy, dry_run=True)
    assert run.scanned == 5
    assert run.deleted == 0
    # the 5 old events remain (plus this run's own RETENTION_RUN audit)
    assert AuditEvent.objects.filter(event_type=EventType.LOGOUT).count() == 5


def test_real_delete_removes_expired():
    _old_audit_events(4)
    policy = _audit_policy()
    run = execute_policy(policy, dry_run=False)
    assert run.deleted == 4
    assert AuditEvent.objects.filter(event_type=EventType.LOGOUT).count() == 0


def test_idempotent_second_run_deletes_nothing():
    _old_audit_events(3)
    policy = _audit_policy()
    execute_policy(policy, dry_run=False)
    run2 = execute_policy(policy, dry_run=False)
    assert run2.scanned == 0
    assert run2.deleted == 0


def test_bounded_by_max_deletes():
    _old_audit_events(5)
    policy = _audit_policy(max_deletes_per_run=2, batch_size=1)
    run = execute_policy(policy, dry_run=False)
    assert run.deleted == 2  # capped
    assert AuditEvent.objects.filter(event_type=EventType.LOGOUT).count() == 3


def test_run_produces_audit_record():
    _old_audit_events(1)
    policy = _audit_policy()
    execute_policy(policy, dry_run=True)
    assert AuditEvent.objects.filter(event_type=EventType.RETENTION_RUN).exists()


def test_kill_switch_skips(settings):
    _old_audit_events(2)
    settings.RETENTION_ENABLED = False
    policy = _audit_policy()
    run = execute_policy(policy, dry_run=False)
    assert run.outcome == RunOutcome.SKIPPED
    assert AuditEvent.objects.filter(event_type=EventType.LOGOUT).count() == 2


def test_disabled_policy_skipped():
    policy = _audit_policy()
    policy.enabled = False
    policy.save()
    run = execute_policy(policy, dry_run=False)
    assert run.outcome == RunOutcome.SKIPPED


def test_failure_recovery(monkeypatch):
    _old_audit_events(2)
    policy = _audit_policy()
    handler = get_handler(DataCategory.SECURITY_AUDIT)
    monkeypatch.setattr(handler, "purge", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    run = execute_policy(policy, dry_run=False)
    assert run.outcome == RunOutcome.FAILED
    assert "boom" in run.error
    # data untouched; a later (unpatched) run still works
    monkeypatch.undo()
    run2 = execute_policy(policy, dry_run=False)
    assert run2.outcome == RunOutcome.SUCCESS
    assert run2.deleted == 2


def test_retention_floor_enforced(api, auth, sysadmin):
    auth(api, sysadmin)
    policy = RetentionPolicy.objects.get(category=DataCategory.SECURITY_AUDIT)
    resp = api.patch(f"/api/v1/retention/policies/{policy.id}", {"retention_days": 5})
    assert resp.status_code == 400  # below the 30-day floor for audit


def test_run_endpoint_dry_run_default(api, auth, sysadmin):
    _old_audit_events(2)
    _audit_policy()
    auth(api, sysadmin)
    policy = RetentionPolicy.objects.get(category=DataCategory.SECURITY_AUDIT)
    resp = api.post(f"/api/v1/retention/policies/{policy.id}/run", {})
    assert resp.status_code == 200
    assert resp.json()["data"]["dry_run"] is True
    assert resp.json()["data"]["deleted"] == 0


def test_retention_requires_system_admin(api, auth, traffic_admin):
    auth(api, traffic_admin)
    assert api.get("/api/v1/retention/policies").status_code == 403


def test_evaluate_retention_task_runs_enabled_policies():
    from apps.retention.tasks import evaluate_retention

    _old_audit_events(2)
    _audit_policy(dry_run_default=False)
    n = evaluate_retention.delay().get(timeout=5)
    assert n >= 1  # at least the audit policy ran
    assert RetentionRun.objects.filter(policy__category=DataCategory.SECURITY_AUDIT).exists()


def test_execute_policy_task_by_id():
    from apps.retention.tasks import execute_policy_task

    _old_audit_events(1)
    policy = _audit_policy()
    run_id = execute_policy_task.delay(str(policy.id), dry_run=True).get(timeout=5)
    run = RetentionRun.objects.get(id=run_id)
    assert run.dry_run is True
    assert run.scanned == 1

"""Celery tasks for retention (Phase 2 §22). Respects ADR-002 (no CV work)."""
from __future__ import annotations

from celery import shared_task

from apps.retention.models import RetentionPolicy
from apps.retention.services import evaluate_all, execute_policy


@shared_task(name="apps.retention.tasks.evaluate_retention")
def evaluate_retention() -> int:
    runs = evaluate_all(source="celery")
    return len(runs)


@shared_task(name="apps.retention.tasks.execute_policy")
def execute_policy_task(policy_id: str, dry_run: bool = True) -> str:
    policy = RetentionPolicy.objects.get(pk=policy_id)
    run = execute_policy(policy, dry_run=dry_run, source="celery")
    return str(run.id)

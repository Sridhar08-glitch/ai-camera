"""
Retention execution engine (Phase 2 §19).

Idempotent (delete-by-cutoff), bounded (batch + max_deletes cap), dry-run capable,
audited (every run writes a RetentionRun + an AuditEvent), and guarded by a global
kill switch. Only categories with a registered handler are acted on.
"""
from __future__ import annotations

from datetime import timedelta

import structlog
from django.conf import settings
from django.utils import timezone

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.retention.models import RetentionPolicy, RetentionRun, RunOutcome
from apps.retention.registry import get_handler

logger = structlog.get_logger("retention")


def execute_policy(policy: RetentionPolicy, *, dry_run: bool, source: str = "celery", request=None) -> RetentionRun:
    run = RetentionRun.objects.create(policy=policy, dry_run=dry_run, source=source)

    def _finalize(outcome, scanned=0, deleted=0, error=""):
        run.outcome = outcome
        run.scanned = scanned
        run.deleted = deleted
        run.error = error[:2000]
        run.finished_at = timezone.now()
        run.save(update_fields=["outcome", "scanned", "deleted", "error", "finished_at"])
        RetentionPolicy.objects.filter(pk=policy.pk).update(last_run_at=run.finished_at)
        record_audit(
            EventType.RETENTION_RUN,
            action="retention_execute",
            request=request,
            source=source,
            target_type="RetentionPolicy",
            target_id=policy.id,
            metadata={
                "category": policy.category,
                "dry_run": dry_run,
                "scanned": scanned,
                "deleted": deleted,
                "outcome": outcome,
            },
        )
        return run

    # Global kill switch.
    if not getattr(settings, "RETENTION_ENABLED", True):
        logger.warning("retention_disabled", policy=str(policy.pk))
        return _finalize(RunOutcome.SKIPPED, error="retention globally disabled")

    if not policy.enabled:
        return _finalize(RunOutcome.SKIPPED, error="policy disabled")

    handler = get_handler(policy.category)
    if handler is None:
        logger.info("retention_no_handler", category=policy.category)
        return _finalize(RunOutcome.SKIPPED, error=f"no handler for {policy.category}")

    cutoff = timezone.now() - timedelta(days=policy.retention_days)
    max_deletes = min(policy.max_deletes_per_run, getattr(settings, "RETENTION_MAX_DELETES_PER_RUN", 100000))

    try:
        result = handler.purge(
            cutoff, batch_size=policy.batch_size, max_deletes=max_deletes, dry_run=dry_run
        )
        return _finalize(RunOutcome.SUCCESS, scanned=result.scanned, deleted=result.deleted)
    except Exception as exc:  # noqa: BLE001 - record and continue (idempotent resume)
        logger.error("retention_failed", category=policy.category, exc_info=exc)
        return _finalize(RunOutcome.FAILED, error=str(exc))


def evaluate_all(*, source: str = "celery") -> list[RetentionRun]:
    """Run every enabled policy, honoring each policy's dry_run_default."""
    runs = []
    for policy in RetentionPolicy.objects.filter(enabled=True):
        runs.append(execute_policy(policy, dry_run=policy.dry_run_default, source=source))
    return runs

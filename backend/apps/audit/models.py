"""
AuditEvent — durable, append-only security/administrative audit record.

Immutability is enforced in three layers (ADR-016):
  1. Application: no update/delete API exists.
  2. ORM: save() rejects updates; delete() raises; manager blocks bulk update/delete.
  3. Database: a BEFORE UPDATE OR DELETE trigger raises (added by migration 0002).
The honest boundary: aitraffic_app owns the table and could DROP the trigger via
DDL; the application never does. See ADR-016.
"""
from __future__ import annotations

from django.db import models

from apps.common.models import UUIDModel


class AuditImmutableError(Exception):
    """Raised on any attempt to modify or delete an audit record."""


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):  # noqa: D401 - block bulk update
        raise AuditImmutableError("AuditEvent rows are immutable; bulk update denied.")

    def delete(self):
        raise AuditImmutableError("AuditEvent rows are immutable; bulk delete denied.")

    def _raw_delete_denied(self, *a, **k):
        raise AuditImmutableError("AuditEvent rows are immutable; raw delete denied.")


class AuditEventManager(models.Manager.from_queryset(AuditEventQuerySet)):
    """Default manager whose querysets refuse update()/delete()."""


class RetentionDeletableManager(models.Manager.from_queryset(models.QuerySet)):
    """
    Escape hatch used ONLY by the retention engine to purge expired audit rows in
    a controlled, bounded, audited way. Not exposed via any API. Keeps the default
    manager fully immutable for all application code.
    """


class EventType(models.TextChoices):
    LOGIN_SUCCESS = "login_success", "Login success"
    LOGIN_FAILURE = "login_failure", "Login failure"
    LOGOUT = "logout", "Logout"
    USER_CREATED = "user_created", "User created"
    USER_UPDATED = "user_updated", "User updated"
    USER_ACTIVATED = "user_activated", "User activated"
    USER_DEACTIVATED = "user_deactivated", "User deactivated"
    ROLE_CHANGED = "role_changed", "Role changed"
    USER_DELETED = "user_deleted", "User deleted"
    RETENTION_RUN = "retention_run", "Retention run executed"
    MODEL_ACTIVATED = "model_activated", "Model version activated"
    MODEL_DEACTIVATED = "model_deactivated", "Model version deactivated"
    ALGORITHM_ACTIVATED = "algorithm_activated", "Algorithm version activated"
    # Phase 6 — detection model governance.
    MODEL_APPROVED = "model_approved", "Model version approved"
    # Phase 6T-A — dataset governance + training provenance.
    DATASET_REGISTERED = "dataset_registered", "Dataset registered"
    DATASET_LICENSE_VERIFIED = "dataset_license_verified", "Dataset license verified"
    DATASET_VERSION_APPROVED = "dataset_version_approved", "Dataset version approved"
    DATASET_VERSION_REJECTED = "dataset_version_rejected", "Dataset version rejected"
    TRAINING_STARTED = "training_started", "Training run started"
    TRAINING_COMPLETED = "training_completed", "Training run completed"
    TRAINING_FAILED = "training_failed", "Training run failed"
    # Phase 3 — traffic network configuration changes.
    NETWORK_CONFIG_CREATED = "network_config_created", "Network config created"
    NETWORK_CONFIG_UPDATED = "network_config_updated", "Network config updated"
    NETWORK_CONFIG_ARCHIVED = "network_config_archived", "Network config archived"
    NETWORK_CONFIG_DELETED = "network_config_deleted", "Network config deleted"
    # Phase 4 — video ingestion.
    VIDEO_UPLOADED = "video_uploaded", "Video uploaded"
    VIDEO_VALIDATION_FAILED = "video_validation_failed", "Video validation failed"
    VIDEO_ARCHIVED = "video_archived", "Video archived"
    VIDEO_DELETED = "video_deleted", "Video deleted"
    # Phase 5 — processing sessions.
    PROCESSING_REQUESTED = "processing_requested", "Processing requested"
    PROCESSING_QUEUED = "processing_queued", "Processing queued"
    PROCESSING_STARTED = "processing_started", "Processing started"
    PROCESSING_PAUSED = "processing_paused", "Processing paused"
    PROCESSING_RESUMED = "processing_resumed", "Processing resumed"
    PROCESSING_CANCEL_REQUESTED = "processing_cancel_requested", "Processing cancellation requested"
    PROCESSING_CANCELLED = "processing_cancelled", "Processing cancelled"
    PROCESSING_STOPPED = "processing_stopped", "Processing stopped"
    PROCESSING_COMPLETED = "processing_completed", "Processing completed"
    PROCESSING_FAILED = "processing_failed", "Processing failed"
    PROCESSING_RETRY_REQUESTED = "processing_retry_requested", "Processing retry requested"


class Outcome(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILURE = "failure", "Failure"
    DENIED = "denied", "Denied"


class AuditEvent(UUIDModel):
    event_type = models.CharField(max_length=48, choices=EventType.choices, db_index=True)
    action = models.CharField(max_length=128)
    outcome = models.CharField(max_length=16, choices=Outcome.choices, default=Outcome.SUCCESS)

    # Actor is referenced BY VALUE (UUID + snapshot), NOT via a foreign key.
    # This keeps audit rows fully immutable: deleting a user never issues an
    # UPDATE/SET NULL against audit_event (which the immutability trigger blocks),
    # and the actor's identity is preserved via the snapshot fields.
    actor_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_email = models.CharField(max_length=254, blank=True, default="")
    actor_role = models.CharField(max_length=32, blank=True, default="")

    target_type = models.CharField(max_length=64, blank=True, default="", db_index=True)
    target_id = models.CharField(max_length=64, blank=True, default="")

    request_id = models.CharField(max_length=64, blank=True, default="")
    source = models.CharField(max_length=16, default="django")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditEventManager()
    retention_objects = RetentionDeletableManager()

    class Meta:
        db_table = "audit_event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["actor_id", "created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.outcome}@{self.created_at:%Y-%m-%dT%H:%M:%S}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditImmutableError("AuditEvent rows are immutable; update denied.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditImmutableError("AuditEvent rows are immutable; delete denied.")

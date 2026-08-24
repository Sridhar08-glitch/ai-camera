"""
AuditedModelViewSet (Phase 3 §21).

Emits a transactional audit event on every privileged mutation. Audit metadata
stores CHANGED FIELD NAMES and old/new config_hash only — never full geometry
arrays (§14). DELETE archives (is_active=False) by default; leaf image-space
resources set `archive_on_delete=False` for a true delete.
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.response import Response

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.common.permissions import IsSystemAdmin
from apps.network.permissions import NetworkReadOrAdminWrite


class AuditedModelViewSet:
    """Mixin — combine with rest_framework.viewsets.ModelViewSet."""

    permission_classes = [NetworkReadOrAdminWrite]
    archive_on_delete = True
    audit_target = "NetworkConfig"  # override per viewset

    def _hash(self, obj):
        return getattr(obj, "config_hash", None)

    def perform_create(self, serializer):
        with transaction.atomic():
            obj = serializer.save()
            record_audit(
                EventType.NETWORK_CONFIG_CREATED,
                action=f"create_{self.audit_target.lower()}",
                request=self.request,
                target_type=self.audit_target,
                target_id=obj.pk,
                metadata={"fields": sorted(serializer.validated_data.keys()),
                          "new_config_hash": self._hash(obj)},
            )

    def perform_update(self, serializer):
        old_hash = self._hash(serializer.instance)
        with transaction.atomic():
            obj = serializer.save()
            record_audit(
                EventType.NETWORK_CONFIG_UPDATED,
                action=f"update_{self.audit_target.lower()}",
                request=self.request,
                target_type=self.audit_target,
                target_id=obj.pk,
                metadata={
                    "changed_fields": sorted(serializer.validated_data.keys()),
                    "old_config_hash": old_hash,
                    "new_config_hash": self._hash(obj),
                    "revision": getattr(obj, "revision", None),
                },
            )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        target_id = instance.pk
        if self.archive_on_delete:
            if not hasattr(instance, "is_active"):
                return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
            with transaction.atomic():
                instance.is_active = False
                instance.save(update_fields=["is_active", "updated_at"])
                record_audit(
                    EventType.NETWORK_CONFIG_ARCHIVED,
                    action=f"archive_{self.audit_target.lower()}",
                    request=request,
                    target_type=self.audit_target,
                    target_id=target_id,
                    metadata={"archived": True},
                )
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Hard delete (leaf image-space / coverage). Guard PROTECTed relations.
        try:
            with transaction.atomic():
                instance.delete()
                record_audit(
                    EventType.NETWORK_CONFIG_DELETED,
                    action=f"delete_{self.audit_target.lower()}",
                    request=request,
                    target_type=self.audit_target,
                    target_id=target_id,
                    metadata={"deleted": True},
                )
        except ProtectedError:
            return Response(
                {"error": {"code": "protected", "message": "Cannot delete: referenced by other configuration. Archive instead."}},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class HardDeleteSystemAdminMixin:
    """For leaf image-space resources: hard delete, restricted to system_admin."""

    archive_on_delete = False

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsSystemAdmin()]
        return [NetworkReadOrAdminWrite()]

"""Governance API (Phase 2 §23). Writes: system_admin. Reads: system_admin/traffic_admin."""
from __future__ import annotations

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.common.permissions import HasAnyRole, IsSystemAdmin
from apps.common.roles import RoleCode
from apps.governance.models import (
    AIModel,
    AIModelVersion,
    AlgorithmDefinition,
    AlgorithmVersion,
    ModelArtifact,
    ModelLifecycle,
    StoredArtifact,
)
from apps.governance.serializers import (
    AIModelSerializer,
    AIModelVersionSerializer,
    AlgorithmDefinitionSerializer,
    AlgorithmVersionSerializer,
    ModelArtifactSerializer,
    StoredArtifactSerializer,
)


class _ReadAdminWriteSysadmin(viewsets.ModelViewSet):
    """Reads for system_admin + traffic_admin; writes for system_admin only."""

    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [IsSystemAdmin()]

        class _ReadRoles(HasAnyRole):
            allowed_roles = frozenset({RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN})

        return [_ReadRoles()]


class AIModelViewSet(_ReadAdminWriteSysadmin):
    queryset = AIModel.objects.all()
    serializer_class = AIModelSerializer


class AIModelVersionViewSet(_ReadAdminWriteSysadmin):
    queryset = AIModelVersion.objects.select_related("model").all()
    serializer_class = AIModelVersionSerializer

    @action(detail=True, methods=["post"], permission_classes=[IsSystemAdmin])
    def approve(self, request, pk=None):
        """Promote an EVALUATED/CANDIDATE version to APPROVED (prerequisite for
        activation). TEST_ONLY versions can never be approved (Phase 6 §30)."""
        version = self.get_object()
        if version.status == ModelLifecycle.TEST_ONLY:
            return Response(
                {"error": {"code": "test_only", "message": "test-only versions cannot be approved"}},
                status=status.HTTP_409_CONFLICT,
            )
        version.status = ModelLifecycle.APPROVED
        version.save(update_fields=["status"])
        record_audit(
            EventType.MODEL_APPROVED, action="approve_model_version", request=request,
            target_type="AIModelVersion", target_id=version.id,
            metadata={"model": version.model.family, "version": version.version},
        )
        return Response(self.get_serializer(version).data)

    @action(detail=True, methods=["post"], permission_classes=[IsSystemAdmin])
    def activate(self, request, pk=None):
        """Activate an APPROVED (or already ACTIVE) version. Only one active per
        family. TEST_ONLY / unapproved versions are refused (production gate)."""
        version = self.get_object()
        if version.status == ModelLifecycle.TEST_ONLY:
            return Response(
                {"error": {"code": "test_only", "message": "test-only versions can never be activated for production"}},
                status=status.HTTP_409_CONFLICT,
            )
        if version.status not in (ModelLifecycle.APPROVED, ModelLifecycle.ACTIVE):
            return Response(
                {"error": {"code": "not_approved", "message": "only APPROVED versions can be activated"}},
                status=status.HTTP_409_CONFLICT,
            )
        with transaction.atomic():
            AIModelVersion.objects.filter(model=version.model).exclude(pk=version.pk).update(
                is_active=False
            )
            AIModelVersion.objects.filter(
                model=version.model, status=ModelLifecycle.ACTIVE
            ).exclude(pk=version.pk).update(status=ModelLifecycle.APPROVED)
            version.is_active = True
            version.status = ModelLifecycle.ACTIVE
            version.save(update_fields=["is_active", "status"])
            record_audit(
                EventType.MODEL_ACTIVATED,
                action="activate_model_version",
                request=request,
                target_type="AIModelVersion",
                target_id=version.id,
                metadata={"model": version.model.family, "version": version.version},
            )
        return Response(self.get_serializer(version).data)


class ModelArtifactViewSet(_ReadAdminWriteSysadmin):
    queryset = ModelArtifact.objects.select_related("model_version").all()
    serializer_class = ModelArtifactSerializer


class AlgorithmDefinitionViewSet(_ReadAdminWriteSysadmin):
    queryset = AlgorithmDefinition.objects.all()
    serializer_class = AlgorithmDefinitionSerializer


class AlgorithmVersionViewSet(_ReadAdminWriteSysadmin):
    queryset = AlgorithmVersion.objects.select_related("definition").all()
    serializer_class = AlgorithmVersionSerializer

    @action(detail=True, methods=["post"], permission_classes=[IsSystemAdmin])
    def activate(self, request, pk=None):
        version = self.get_object()
        with transaction.atomic():
            AlgorithmVersion.objects.filter(definition=version.definition).exclude(
                pk=version.pk
            ).update(is_active=False)
            # is_active toggled via queryset update to respect immutable save().
            AlgorithmVersion.objects.filter(pk=version.pk).update(is_active=True)
            record_audit(
                EventType.ALGORITHM_ACTIVATED,
                action="activate_algorithm_version",
                request=request,
                target_type="AlgorithmVersion",
                target_id=version.id,
                metadata={"definition": version.definition.key, "version": version.version},
            )
        version.refresh_from_db()
        return Response(self.get_serializer(version).data)


class StoredArtifactViewSet(_ReadAdminWriteSysadmin):
    queryset = StoredArtifact.objects.all()
    serializer_class = StoredArtifactSerializer

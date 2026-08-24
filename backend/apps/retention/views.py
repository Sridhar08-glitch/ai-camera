"""Retention API (Phase 2 §23). system_admin only. Real deletion needs dry_run=false."""
from __future__ import annotations

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import IsSystemAdmin
from apps.retention.models import RetentionPolicy, RetentionRun
from apps.retention.serializers import RetentionPolicySerializer, RetentionRunSerializer
from apps.retention.services import execute_policy


class RetentionPolicyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsSystemAdmin]
    serializer_class = RetentionPolicySerializer
    queryset = RetentionPolicy.objects.all()
    http_method_names = ["get", "patch", "post", "head", "options"]

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        policy = self.get_object()
        # Dry-run is the default; a real delete requires an explicit dry_run=false.
        dry_run = request.data.get("dry_run", True)
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() not in ("false", "0", "no")
        run = execute_policy(policy, dry_run=bool(dry_run), source="api", request=request)
        return Response(RetentionRunSerializer(run).data)


class RetentionRunViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsSystemAdmin]
    serializer_class = RetentionRunSerializer

    def get_queryset(self):
        qs = RetentionRun.objects.select_related("policy").all()
        if self.request.query_params.get("policy"):
            qs = qs.filter(policy_id=self.request.query_params["policy"])
        return qs

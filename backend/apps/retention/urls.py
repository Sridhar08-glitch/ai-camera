"""Retention routes under /api/v1/retention/."""
from django.urls import path

from apps.retention.views import RetentionPolicyViewSet, RetentionRunViewSet

_policy_list = RetentionPolicyViewSet.as_view({"get": "list"})
_policy_detail = RetentionPolicyViewSet.as_view({"get": "retrieve", "patch": "partial_update"})
_policy_run = RetentionPolicyViewSet.as_view({"post": "run"})
_run_list = RetentionRunViewSet.as_view({"get": "list"})
_run_detail = RetentionRunViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("policies", _policy_list, name="retention-policy-list"),
    path("policies/<uuid:pk>", _policy_detail, name="retention-policy-detail"),
    path("policies/<uuid:pk>/run", _policy_run, name="retention-policy-run"),
    path("runs", _run_list, name="retention-run-list"),
    path("runs/<uuid:pk>", _run_detail, name="retention-run-detail"),
]

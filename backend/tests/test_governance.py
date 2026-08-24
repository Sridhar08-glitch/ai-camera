"""AI model governance + provenance + artifact safety tests."""
from __future__ import annotations

import pytest

from apps.audit.models import AuditEvent, EventType
from apps.governance.models import AIModelVersion

pytestmark = pytest.mark.django_db


def _model_payload():
    return {"family": "yolo", "task": "detection", "provider": "ultralytics", "description": "d"}


def test_create_model_and_version(api, auth, sysadmin):
    auth(api, sysadmin)
    m = api.post("/api/v1/governance/models", _model_payload())
    assert m.status_code == 201
    mid = m.json()["data"]["id"]
    v = api.post(
        "/api/v1/governance/model-versions",
        {"model": mid, "version": "8n", "provenance": "pretrained", "license": "AGPL"},
    )
    assert v.status_code == 201
    assert v.json()["data"]["provenance"] == "pretrained"


def test_version_uniqueness(api, auth, sysadmin):
    auth(api, sysadmin)
    mid = api.post("/api/v1/governance/models", _model_payload()).json()["data"]["id"]
    body = {"model": mid, "version": "8n", "provenance": "pretrained"}
    assert api.post("/api/v1/governance/model-versions", body).status_code == 201
    assert api.post("/api/v1/governance/model-versions", body).status_code == 400


def test_provenance_required(api, auth, sysadmin):
    auth(api, sysadmin)
    mid = api.post("/api/v1/governance/models", _model_payload()).json()["data"]["id"]
    resp = api.post("/api/v1/governance/model-versions", {"model": mid, "version": "x"})
    assert resp.status_code == 400  # provenance missing


def test_artifact_valid_path_and_checksum(api, auth, sysadmin):
    auth(api, sysadmin)
    mid = api.post("/api/v1/governance/models", _model_payload()).json()["data"]["id"]
    vid = api.post(
        "/api/v1/governance/model-versions",
        {"model": mid, "version": "8n", "provenance": "pretrained"},
    ).json()["data"]["id"]
    resp = api.post(
        "/api/v1/governance/model-artifacts",
        {"model_version": vid, "kind": "weights", "path": "models/yolo8n.pt",
         "checksum_sha256": "a" * 64, "size_bytes": 1234},
    )
    assert resp.status_code == 201


def test_artifact_path_traversal_rejected(api, auth, sysadmin):
    auth(api, sysadmin)
    mid = api.post("/api/v1/governance/models", _model_payload()).json()["data"]["id"]
    vid = api.post(
        "/api/v1/governance/model-versions",
        {"model": mid, "version": "8n", "provenance": "pretrained"},
    ).json()["data"]["id"]
    resp = api.post(
        "/api/v1/governance/model-artifacts",
        {"model_version": vid, "kind": "weights", "path": "../../../../etc/passwd"},
    )
    assert resp.status_code == 400


def test_activation_single_active_and_audited(api, auth, sysadmin):
    auth(api, sysadmin)
    mid = api.post("/api/v1/governance/models", _model_payload()).json()["data"]["id"]
    v1 = api.post("/api/v1/governance/model-versions", {"model": mid, "version": "1", "provenance": "pretrained"}).json()["data"]["id"]
    v2 = api.post("/api/v1/governance/model-versions", {"model": mid, "version": "2", "provenance": "pretrained"}).json()["data"]["id"]
    # Phase 6 production gate (§30): a DRAFT version cannot be activated directly.
    assert api.post(f"/api/v1/governance/model-versions/{v1}/activate").status_code == 409
    # Approve first, then activate.
    assert api.post(f"/api/v1/governance/model-versions/{v1}/approve").status_code == 200
    assert api.post(f"/api/v1/governance/model-versions/{v2}/approve").status_code == 200
    assert api.post(f"/api/v1/governance/model-versions/{v1}/activate").status_code == 200
    assert api.post(f"/api/v1/governance/model-versions/{v2}/activate").status_code == 200
    active = AIModelVersion.objects.filter(model_id=mid, is_active=True)
    assert active.count() == 1 and str(active.first().id) == v2
    # Activating v2 demotes the previously-active v1 back to APPROVED (not ACTIVE).
    v1_obj = AIModelVersion.objects.get(id=v1)
    assert v1_obj.status == "approved" and v1_obj.is_active is False
    assert AuditEvent.objects.filter(event_type=EventType.MODEL_ACTIVATED).count() == 2
    assert AuditEvent.objects.filter(event_type=EventType.MODEL_APPROVED).count() == 2


def test_write_requires_system_admin(api, auth, traffic_admin, operator):
    auth(api, traffic_admin)
    assert api.post("/api/v1/governance/models", _model_payload()).status_code == 403
    # but traffic_admin may read
    assert api.get("/api/v1/governance/models").status_code == 200
    auth(api, operator)
    assert api.get("/api/v1/governance/models").status_code == 403

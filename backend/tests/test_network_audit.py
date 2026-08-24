"""Network audit integration + no-large-geometry-in-metadata guarantee."""
from __future__ import annotations

import json

import pytest

from apps.audit.models import AuditEvent, EventType

pytestmark = pytest.mark.django_db


def _mk(api, path, **body):
    return api.post(f"/api/v1/network/{path}", body)


@pytest.fixture
def camera(api, auth, sysadmin):
    auth(api, sysadmin)
    city = _mk(api, "cities", name="A", code="A").json()["data"]
    return _mk(api, "cameras", city=city["id"], name="C", code="C").json()["data"]


def test_create_emits_audit(api, camera):
    ev = AuditEvent.objects.filter(event_type=EventType.NETWORK_CONFIG_CREATED, target_type="Camera").first()
    assert ev is not None
    assert ev.target_id == camera["id"]
    assert "fields" in ev.metadata


def test_update_emits_audit_with_hash_pair(api, camera):
    api.patch(f"/api/v1/network/cameras/{camera['id']}", {"bearing_deg": 45})
    ev = AuditEvent.objects.filter(event_type=EventType.NETWORK_CONFIG_UPDATED, target_id=camera["id"]).first()
    assert ev is not None
    assert "old_config_hash" in ev.metadata and "new_config_hash" in ev.metadata
    assert ev.metadata["old_config_hash"] != ev.metadata["new_config_hash"]


def test_archive_emits_audit(api, camera):
    api.delete(f"/api/v1/network/cameras/{camera['id']}")
    assert AuditEvent.objects.filter(event_type=EventType.NETWORK_CONFIG_ARCHIVED, target_id=camera["id"]).exists()


def test_audit_metadata_contains_no_full_geometry(api, camera):
    big_polygon = {"space": "image_normalized", "coordinates": [[round(i / 1000, 3), 0.5] for i in range(1, 200)]}
    roi = _mk(api, "regions-of-interest", camera=camera["id"], name="big", polygon=big_polygon).json()["data"]
    ev = AuditEvent.objects.filter(target_type="RegionOfInterest", target_id=roi["id"]).first()
    assert ev is not None
    blob = json.dumps(ev.metadata)
    # The polygon coordinate arrays must NOT be duplicated into audit metadata.
    assert "coordinates" not in blob
    assert "0.199" not in blob  # a coordinate value from the polygon
    # only field names + hash are present
    assert "fields" in ev.metadata or "new_config_hash" in ev.metadata

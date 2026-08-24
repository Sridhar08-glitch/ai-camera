"""Configuration versioning: revision + deterministic config_hash (ADR-021)."""
from __future__ import annotations

import pytest

from apps.common.versioning import canonical_hash
from apps.network.models import Camera

pytestmark = pytest.mark.django_db


def _mk(api, path, **body):
    return api.post(f"/api/v1/network/{path}", body)


@pytest.fixture
def camera(api, auth, sysadmin):
    auth(api, sysadmin)
    city = _mk(api, "cities", name="V", code="V").json()["data"]
    cam = _mk(api, "cameras", city=city["id"], name="C", code="C", bearing_deg=90).json()["data"]
    return cam


def test_canonical_hash_is_deterministic_and_order_independent():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})
    assert canonical_hash({"a": 1}) != canonical_hash({"a": 2})


def test_new_entity_starts_at_revision_1(camera):
    obj = Camera.objects.get(id=camera["id"])
    assert obj.revision == 1
    assert len(obj.config_hash) == 64


def test_versioned_field_change_bumps_revision(api, camera):
    r = api.patch(f"/api/v1/network/cameras/{camera['id']}", {"bearing_deg": 180})
    assert r.status_code == 200
    obj = Camera.objects.get(id=camera["id"])
    assert obj.revision == 2
    assert obj.config_hash != camera["config_hash"]


def test_non_versioned_field_change_does_not_bump(api, camera):
    r = api.patch(f"/api/v1/network/cameras/{camera['id']}", {"name": "Renamed"})
    assert r.status_code == 200
    obj = Camera.objects.get(id=camera["id"])
    assert obj.revision == 1  # name is not version-controlled
    assert obj.config_hash == camera["config_hash"]


def test_is_active_change_does_not_bump(api, camera):
    api.delete(f"/api/v1/network/cameras/{camera['id']}")  # archive -> is_active False
    obj = Camera.objects.get(id=camera["id"])
    assert obj.revision == 1

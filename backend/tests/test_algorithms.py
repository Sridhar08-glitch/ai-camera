"""Algorithm version governance tests."""
from __future__ import annotations

import pytest

from apps.governance.checksums import canonical_config_hash
from apps.governance.models import AlgorithmDefinition, AlgorithmVersion

pytestmark = pytest.mark.django_db


def test_config_hash_is_reproducible():
    a = canonical_config_hash({"b": 1, "a": 2})
    b = canonical_config_hash({"a": 2, "b": 1})  # key order independent
    assert a == b
    assert a != canonical_config_hash({"a": 2, "b": 3})


def test_create_definition_and_version(api, auth, sysadmin):
    auth(api, sysadmin)
    d = api.post("/api/v1/governance/algorithms", {"key": "congestion_v1", "name": "Congestion", "category": "congestion"})
    assert d.status_code == 201
    did = d.json()["data"]["id"]
    v = api.post("/api/v1/governance/algorithm-versions", {"definition": did, "version": "1.0", "config": {"threshold": 0.7}})
    assert v.status_code == 201
    assert len(v.json()["data"]["config_hash"]) == 64


def test_version_uniqueness(api, auth, sysadmin):
    auth(api, sysadmin)
    did = api.post("/api/v1/governance/algorithms", {"key": "queue_v1", "name": "Q"}).json()["data"]["id"]
    body = {"definition": did, "version": "1.0", "config": {}}
    assert api.post("/api/v1/governance/algorithm-versions", body).status_code == 201
    assert api.post("/api/v1/governance/algorithm-versions", body).status_code == 400


def test_version_is_immutable():
    d = AlgorithmDefinition.objects.create(key="speed_v1", name="Speed")
    v = AlgorithmVersion.objects.create(definition=d, version="1", config={}, config_hash="x")
    v.description = "changed"
    with pytest.raises(ValueError):
        v.save()

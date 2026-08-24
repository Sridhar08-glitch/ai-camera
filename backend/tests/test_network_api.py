"""Network API: permissions, filtering, pagination, export, coverage M:N."""
from __future__ import annotations

import pytest

from apps.common.roles import RoleCode

pytestmark = pytest.mark.django_db


def _mk(api, path, **body):
    return api.post(f"/api/v1/network/{path}", body)


@pytest.fixture
def city(api, auth, sysadmin):
    auth(api, sysadmin)
    return _mk(api, "cities", name="City", code="CITY").json()["data"]


def test_read_allowed_for_all_roles(api, auth, make_user, city):
    for role in RoleCode.values:
        auth(api, make_user(role, email=f"r-{role}@ex.com"))
        assert api.get("/api/v1/network/cities").status_code == 200


def test_write_requires_admin(api, auth, make_user):
    for role in RoleCode.values:
        auth(api, make_user(role, email=f"w-{role}@ex.com"))
        r = _mk(api, "cities", name="X", code=f"C-{role}")
        if role in (RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN):
            assert r.status_code == 201
        else:
            assert r.status_code == 403


def test_traffic_admin_can_write(api, auth, traffic_admin):
    auth(api, traffic_admin)
    assert _mk(api, "cities", name="TA", code="TA").status_code == 201


def test_filtering_zones_by_city(api, auth, sysadmin, city):
    other = _mk(api, "cities", name="Other", code="OTHER").json()["data"]
    _mk(api, "zones", city=city["id"], name="Z1", code="Z1")
    _mk(api, "zones", city=other["id"], name="Z2", code="Z2")
    resp = api.get(f"/api/v1/network/zones?city={city['id']}")
    data = resp.json()["data"]
    assert len(data) == 1 and data[0]["code"] == "Z1"


def test_pagination_meta(api, auth, sysadmin):
    auth(api, sysadmin)
    for i in range(3):
        _mk(api, "cities", name=f"P{i}", code=f"P{i}")
    resp = api.get("/api/v1/network/cities?page_size=2")
    body = resp.json()
    assert "meta" in body and body["meta"]["pagination"]["page_size"] == 2
    assert len(body["data"]) == 2


def test_is_active_filter(api, auth, sysadmin, city):
    api.delete(f"/api/v1/network/cities/{city['id']}")  # archive
    active = api.get("/api/v1/network/cities?is_active=true").json()["data"]
    assert all(c["is_active"] for c in active)


def test_camera_lane_coverage_many_to_many(api, auth, sysadmin, city):
    road = _mk(api, "roads", city=city["id"], name="R", code="R").json()["data"]
    seg = _mk(api, "road-segments", road=road["id"]).json()["data"]
    lane1 = _mk(api, "lanes", road_segment=seg["id"], lane_index=1, direction="forward").json()["data"]
    lane2 = _mk(api, "lanes", road_segment=seg["id"], lane_index=2, direction="forward").json()["data"]
    cam1 = _mk(api, "cameras", city=city["id"], name="C1", code="C1").json()["data"]
    cam2 = _mk(api, "cameras", city=city["id"], name="C2", code="C2").json()["data"]
    # one camera -> many lanes
    assert _mk(api, "camera-coverages", camera=cam1["id"], lane=lane1["id"]).status_code == 201
    assert _mk(api, "camera-coverages", camera=cam1["id"], lane=lane2["id"]).status_code == 201
    # one lane -> many cameras
    assert _mk(api, "camera-coverages", camera=cam2["id"], lane=lane1["id"]).status_code == 201
    # duplicate (camera,lane) rejected
    assert _mk(api, "camera-coverages", camera=cam1["id"], lane=lane1["id"]).status_code == 400


def test_city_export(api, auth, sysadmin, city):
    road = _mk(api, "roads", city=city["id"], name="R", code="R").json()["data"]
    _mk(api, "road-segments", road=road["id"])
    _mk(api, "cameras", city=city["id"], name="C", code="C")
    resp = api.get(f"/api/v1/network/cities/{city['id']}/export")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["city"]["code"] == "CITY"
    assert len(data["roads"]) == 1
    assert len(data["roads"][0]["segments"]) == 1
    assert len(data["cameras"]) == 1


def test_unauthenticated_rejected(api):
    assert api.get("/api/v1/network/cities").status_code == 401

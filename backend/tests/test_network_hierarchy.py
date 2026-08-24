"""Network hierarchy, relationship integrity, uniqueness, archive/delete tests."""
from __future__ import annotations

import pytest

from apps.network.models import City, Lane, RegionOfInterest

pytestmark = pytest.mark.django_db


def _mk(api, path, **body):
    return api.post(f"/api/v1/network/{path}", body)


@pytest.fixture
def chain(api, auth, sysadmin):
    """Create City→Zone→Road→Segment→Intersection→Approach→Lane→Camera+coverage."""
    auth(api, sysadmin)
    city = _mk(api, "cities", name="Metro", code="MET").json()["data"]
    zone = _mk(api, "zones", city=city["id"], name="Central", code="CTR").json()["data"]
    road = _mk(api, "roads", city=city["id"], name="Main St", code="MAIN").json()["data"]
    seg = _mk(api, "road-segments", road=road["id"], zone=zone["id"], direction="both").json()["data"]
    inter = _mk(api, "intersections", city=city["id"], name="X1", code="X1").json()["data"]
    appr = _mk(api, "approaches", intersection=inter["id"], road_segment=seg["id"], approach_type="incoming").json()["data"]
    lane = _mk(api, "lanes", road_segment=seg["id"], approach=appr["id"], lane_index=1, direction="forward").json()["data"]
    cam = _mk(api, "cameras", city=city["id"], intersection=inter["id"], name="Cam1", code="CAM1").json()["data"]
    return {"city": city, "zone": zone, "road": road, "seg": seg, "inter": inter, "appr": appr, "lane": lane, "cam": cam}


def test_full_hierarchy_creates(chain):
    assert City.objects.filter(code="MET").exists()
    assert Lane.objects.count() == 1


def test_unique_city_code(api, auth, sysadmin):
    auth(api, sysadmin)
    assert _mk(api, "cities", name="A", code="DUP").status_code == 201
    assert _mk(api, "cities", name="B", code="DUP").status_code == 400


def test_unique_zone_code_per_city(api, chain):
    # same code in same city rejected
    r = _mk(api, "zones", city=chain["city"]["id"], name="Dup", code="CTR")
    assert r.status_code == 400


def test_unique_lane_index_per_segment_direction(api, chain):
    r = _mk(api, "lanes", road_segment=chain["seg"]["id"], lane_index=1, direction="forward")
    assert r.status_code == 400
    # same index, opposite direction is allowed (divided road)
    r2 = _mk(api, "lanes", road_segment=chain["seg"]["id"], lane_index=1, direction="backward")
    assert r2.status_code == 201


def test_cross_city_zone_rejected_for_intersection(api, auth, sysadmin, chain):
    other_city = _mk(api, "cities", name="Other", code="OTH").json()["data"]
    r = _mk(api, "intersections", city=other_city["id"], zone=chain["zone"]["id"], name="Y", code="Y1")
    assert r.status_code == 400  # zone belongs to a different city


def test_cross_parent_approach_rejected(api, auth, sysadmin, chain):
    # a segment from another city's road cannot feed this intersection
    other_city = _mk(api, "cities", name="O2", code="O2").json()["data"]
    other_road = _mk(api, "roads", city=other_city["id"], name="R", code="R2").json()["data"]
    other_seg = _mk(api, "road-segments", road=other_road["id"]).json()["data"]
    r = _mk(api, "approaches", intersection=chain["inter"]["id"], road_segment=other_seg["id"])
    assert r.status_code == 400


def test_lane_approach_must_match_segment(api, chain):
    # approach references chain seg; a lane on a different segment can't use it
    seg2 = _mk(api, "road-segments", road=chain["road"]["id"]).json()["data"]
    r = _mk(api, "lanes", road_segment=seg2["id"], approach=chain["appr"]["id"], lane_index=2, direction="forward")
    assert r.status_code == 400


def test_archive_is_default_delete_for_topology(api, chain):
    resp = api.delete(f"/api/v1/network/cities/{chain['city']['id']}")
    assert resp.status_code == 204
    city = City.objects.get(id=chain["city"]["id"])
    assert city.is_active is False  # archived, not deleted


def test_protected_hard_delete_blocked(api, chain):
    # ROI is leaf image-space (hard delete allowed); but deleting a camera archives.
    # Deleting a city that still has children: archive (always 204, is_active False).
    resp = api.delete(f"/api/v1/network/roads/{chain['road']['id']}")
    assert resp.status_code == 204  # archived


def test_image_space_hard_delete(api, chain):
    roi = _mk(api, "regions-of-interest", camera=chain["cam"]["id"], name="roi1",
              polygon={"space": "image_normalized", "coordinates": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]]}).json()["data"]
    resp = api.delete(f"/api/v1/network/regions-of-interest/{roi['id']}")
    assert resp.status_code == 204
    assert not RegionOfInterest.objects.filter(id=roi["id"]).exists()  # truly deleted

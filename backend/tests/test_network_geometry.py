"""Geometry validation + coordinate-space separation tests."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db


def _mk(api, path, **body):
    return api.post(f"/api/v1/network/{path}", body)


@pytest.fixture
def camera(api, auth, sysadmin):
    auth(api, sysadmin)
    city = _mk(api, "cities", name="G", code="GEO").json()["data"]
    return _mk(api, "cameras", city=city["id"], name="C", code="C1").json()["data"]


def test_valid_geo_latlng(api, auth, sysadmin):
    auth(api, sysadmin)
    r = _mk(api, "cities", name="Ok", code="OK", center_lat="40.7", center_lng="-74.0")
    assert r.status_code == 201


def test_out_of_range_latitude_rejected(api, auth, sysadmin):
    auth(api, sysadmin)
    r = _mk(api, "cities", name="Bad", code="BAD", center_lat="120.0", center_lng="0.0")
    assert r.status_code == 400


def test_out_of_range_longitude_rejected(api, auth, sysadmin):
    auth(api, sysadmin)
    r = _mk(api, "cities", name="Bad2", code="BAD2", center_lat="0.0", center_lng="200.0")
    assert r.status_code == 400


def test_valid_normalized_polygon(api, camera):
    r = _mk(api, "regions-of-interest", camera=camera["id"], name="ok",
            polygon={"space": "image_normalized", "coordinates": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]})
    assert r.status_code == 201


def test_out_of_range_image_coord_rejected(api, camera):
    r = _mk(api, "regions-of-interest", camera=camera["id"], name="bad",
            polygon={"space": "image_normalized", "coordinates": [[0.1, 0.1], [1.5, 0.1], [0.9, 0.9]]})
    assert r.status_code == 400


def test_polygon_needs_three_vertices(api, camera):
    r = _mk(api, "regions-of-interest", camera=camera["id"], name="tri",
            polygon={"space": "image_normalized", "coordinates": [[0.1, 0.1], [0.2, 0.2]]})
    assert r.status_code == 400


def test_coordinate_space_mismatch_rejected(api, camera):
    # geo coords supplied where image-normalized expected
    r = _mk(api, "regions-of-interest", camera=camera["id"], name="mismatch",
            polygon={"space": "geo", "coordinates": [[-74, 40], [-73, 40], [-73, 41]]})
    assert r.status_code == 400


def test_degenerate_counting_line_rejected(api, camera):
    r = _mk(api, "counting-lines", camera=camera["id"], name="deg",
            start={"x": 0.5, "y": 0.5}, end={"x": 0.5, "y": 0.5})
    assert r.status_code == 400


def test_stop_line_requires_two_points(api, camera):
    r = _mk(api, "stop-lines", camera=camera["id"], name="s1",
            line={"space": "image_normalized", "coordinates": [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]]})
    assert r.status_code == 400


def test_oversized_geometry_rejected(api, camera):
    huge = {"space": "image_normalized", "coordinates": [[0.5, 0.5]] * 600}
    r = _mk(api, "regions-of-interest", camera=camera["id"], name="huge", polygon=huge)
    assert r.status_code == 400


def test_duplicate_consecutive_points_rejected(api, camera):
    r = _mk(api, "regions-of-interest", camera=camera["id"], name="dup",
            polygon={"space": "image_normalized", "coordinates": [[0.1, 0.1], [0.1, 0.1], [0.9, 0.9]]})
    assert r.status_code == 400

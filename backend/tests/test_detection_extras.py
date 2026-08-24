"""Phase 6 — detection retention handler + params validation + taxonomy."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.common.datacategories import DataCategory
from apps.processing.models import FrameDetectionBatch
from apps.processing.retention_handlers import DetectionMetadataRetentionHandler
from apps.processing.runtime.pipeline import run_session
from apps.processing.services.claim import claim_next
from apps.processing.services.params import ParamsError, normalize_params
from apps.processing.services.session import create_session
from apps.retention.registry import get_handler
from tests._processing_helpers import make_valid_video

pytestmark = pytest.mark.django_db


def _make_batches(operator):
    video = make_valid_video(fps=5, seconds=1.0)
    session = create_session(
        video_id=video.id,
        params={"processor": "detector", "sampling": {"mode": "every_frame"},
                "detector": {"model_version_id": "test"}},
        actor=operator,
    )
    run_session(claim_next("test-runtime"))
    return session


def test_retention_handler_registered():
    assert get_handler(DataCategory.DETECTION_METADATA) is not None


def test_retention_purges_detection_batches(vstorage, operator):
    session = _make_batches(operator)
    assert FrameDetectionBatch.objects.filter(session=session).count() == 5
    handler = DetectionMetadataRetentionHandler()
    future = timezone.now() + timedelta(days=1)

    assert handler.count(future) == 5
    # dry-run deletes nothing
    dry = handler.purge(future, batch_size=100, max_deletes=100, dry_run=True)
    assert dry.scanned == 5 and dry.deleted == 0
    assert FrameDetectionBatch.objects.count() == 5
    # real purge, bounded by max_deletes
    res = handler.purge(future, batch_size=100, max_deletes=3, dry_run=False)
    assert res.deleted == 3
    assert FrameDetectionBatch.objects.count() == 2


def test_retention_respects_cutoff(vstorage, operator):
    _make_batches(operator)
    past = timezone.now() - timedelta(days=1)  # nothing older than yesterday
    handler = DetectionMetadataRetentionHandler()
    assert handler.count(past) == 0
    res = handler.purge(past, batch_size=100, max_deletes=100, dry_run=False)
    assert res.deleted == 0
    assert FrameDetectionBatch.objects.count() == 5


# ---- params validation ----

def test_params_detector_defaults_to_test_provider():
    p = normalize_params({"processor": "detector"})
    assert p["detector"] == {"model_version_id": "test"}


def test_params_detector_thresholds():
    p = normalize_params({"processor": "detector",
                          "detector": {"model_version_id": "test", "conf": 0.4, "iou": 0.6}})
    assert p["detector"]["conf"] == 0.4 and p["detector"]["iou"] == 0.6


@pytest.mark.parametrize("bad", [
    {"processor": "noop", "detector": {"model_version_id": "test"}},          # detector on non-detector
    {"processor": "detector", "detector": {"conf": 2.0}},                     # conf out of range
    {"processor": "detector", "detector": {"model_version_id": ""}},          # empty selector
    {"processor": "detector", "detector": {"bogus": 1}},                      # unknown key
])
def test_params_detector_rejections(bad):
    with pytest.raises(ParamsError):
        normalize_params(bad)

"""Phase 6 — detector pipeline integration on REAL decodable video.

Runs the actual CV pipeline (decode → sample → DetectionFrameProcessor → persist)
with the deterministic TEST provider and with a governed project-created ONNX TEST
model, then asserts durable FrameDetectionBatch rows. No third-party weights.
"""
from __future__ import annotations

import pytest

from apps.processing.models import FrameDetectionBatch, ProcessingSession
from apps.processing.runtime.pipeline import run_session
from apps.processing.services.claim import claim_next
from apps.processing.services.session import create_session
from apps.processing.states import ProcessingState
from apps.processing.taxonomy import TAXONOMY_VERSION
from tests._detector_helpers import make_onnx_model_version
from tests._processing_helpers import make_valid_video

pytestmark = pytest.mark.django_db


def _run(video_id, operator, params):
    session = create_session(video_id=video_id, params=params, actor=operator)
    claimed = claim_next("test-runtime")
    assert claimed is not None and claimed.id == session.id
    return run_session(claimed), session


def test_detector_test_provider_persists(vstorage, operator):
    video = make_valid_video(fps=6, seconds=1.0)  # 6 frames
    state, session = _run(video.id, operator, {
        "processor": "detector",
        "sampling": {"mode": "every_frame"},
        "detector": {"model_version_id": "test"},
    })
    assert state == ProcessingState.COMPLETED
    batches = list(FrameDetectionBatch.objects.filter(session=session).order_by("source_frame_index"))
    assert len(batches) == 6
    for b in batches:
        assert b.is_test_provider is True
        assert b.provider_name == "test"
        assert b.taxonomy_version == TAXONOMY_VERSION
        assert b.detection_count == len(b.detections) >= 1
        assert b.model_version is None
        for det in b.detections:
            assert det["bbox_format"] == "normalized_xyxy"
            assert 0.0 <= det["confidence"] <= 1.0


def test_detector_batched_persistence_all_frames(vstorage, operator, settings):
    # Force multiple bulk_create flushes (persist_every_n small vs frame count).
    settings.CV_DETECTOR_PERSIST_EVERY_N = 3
    video = make_valid_video(fps=10, seconds=1.0)  # 10 frames
    state, session = _run(video.id, operator, {
        "processor": "detector", "sampling": {"mode": "every_frame"},
        "detector": {"model_version_id": "test"},
    })
    assert state == ProcessingState.COMPLETED
    assert FrameDetectionBatch.objects.filter(session=session).count() == 10
    # frame indices are unique + complete (0..9)
    idx = sorted(FrameDetectionBatch.objects.filter(session=session)
                 .values_list("source_frame_index", flat=True))
    assert idx == list(range(10))


def test_detector_onnx_governed_model_persists(vstorage, operator, settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT, is_active=True)
    video = make_valid_video(fps=5, seconds=1.0)  # 5 frames
    state, session = _run(video.id, operator, {
        "processor": "detector", "sampling": {"mode": "every_frame"},
        "detector": {"model_version_id": str(version.id)},
    })
    assert state == ProcessingState.COMPLETED
    batches = list(FrameDetectionBatch.objects.filter(session=session))
    assert len(batches) == 5
    for b in batches:
        assert b.is_test_provider is False
        assert b.provider_name == "phase6-test-detector"
        assert str(b.model_version_id) == str(version.id)
        assert b.detection_count == 2  # const test graph emits 2 boxes


def test_detector_empty_detections_not_failure(vstorage, operator, settings, tmp_path):
    settings.ARTIFACT_ROOT = str(tmp_path / "artifacts")
    version = make_onnx_model_version(settings.ARTIFACT_ROOT, is_active=True)
    video = make_valid_video(fps=4, seconds=1.0)
    # conf threshold above the const graph's scores → every frame is empty, but valid.
    state, session = _run(video.id, operator, {
        "processor": "detector", "sampling": {"mode": "every_frame"},
        "detector": {"model_version_id": str(version.id), "conf": 0.99},
    })
    assert state == ProcessingState.COMPLETED
    batches = FrameDetectionBatch.objects.filter(session=session)
    assert batches.count() == 4
    assert all(b.detection_count == 0 for b in batches)
    s = ProcessingSession.objects.get(pk=session.pk)
    assert s.error_code == ""  # empty != failure

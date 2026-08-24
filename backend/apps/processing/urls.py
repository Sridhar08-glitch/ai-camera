"""Processing routes under /api/v1/ (Phase 5 §30)."""
from django.urls import path

from apps.processing.views import ProcessingSessionViewSet, RuntimeStatusView

_list = ProcessingSessionViewSet.as_view({"get": "list", "post": "create"})
_detail = ProcessingSessionViewSet.as_view({"get": "retrieve"})
_cancel = ProcessingSessionViewSet.as_view({"post": "cancel"})
_stop = ProcessingSessionViewSet.as_view({"post": "stop"})
_pause = ProcessingSessionViewSet.as_view({"post": "pause"})
_resume = ProcessingSessionViewSet.as_view({"post": "resume"})
_retry = ProcessingSessionViewSet.as_view({"post": "retry"})
_snapshot = ProcessingSessionViewSet.as_view({"get": "snapshot"})
_detections = ProcessingSessionViewSet.as_view({"get": "detections"})
_detection_frame = ProcessingSessionViewSet.as_view({"get": "detection_frame"})

urlpatterns = [
    path("processing-sessions", _list, name="processing-session-list"),
    path("processing-sessions/<uuid:pk>", _detail, name="processing-session-detail"),
    path("processing-sessions/<uuid:pk>/cancel", _cancel, name="processing-session-cancel"),
    path("processing-sessions/<uuid:pk>/stop", _stop, name="processing-session-stop"),
    path("processing-sessions/<uuid:pk>/pause", _pause, name="processing-session-pause"),
    path("processing-sessions/<uuid:pk>/resume", _resume, name="processing-session-resume"),
    path("processing-sessions/<uuid:pk>/retry", _retry, name="processing-session-retry"),
    path("processing-sessions/<uuid:pk>/snapshot", _snapshot, name="processing-session-snapshot"),
    path("processing-sessions/<uuid:pk>/detections", _detections, name="processing-session-detections"),
    path("processing-sessions/<uuid:pk>/detections/<int:frame_index>", _detection_frame,
         name="processing-session-detection-frame"),
    path("processing/runtime-status", RuntimeStatusView.as_view(), name="processing-runtime-status"),
]

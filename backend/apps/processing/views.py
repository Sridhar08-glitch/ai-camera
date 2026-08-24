"""
Processing session API (Phase 5 §30/§33). Session is a first-class resource under
/api/v1/processing-sessions. State is never settable directly; command endpoints
set requested_action (the CV runtime performs the transition).
"""
from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.processing.models import FrameDetectionBatch, ProcessingSession
from apps.processing.permissions import CanControlProcessing, CanReadProcessing
from apps.processing.serializers import (
    CreateSessionSerializer,
    DetectionBatchSerializer,
    ProcessingSessionSerializer,
    SnapshotMetadataSerializer,
)
from apps.processing.services import commands
from apps.processing.services.params import ParamsError
from apps.processing.services.session import SessionError, create_session, retry_session


def _error(code: str, message: str, status_code: int):
    return Response({"error": {"code": code, "message": message}}, status=status_code)


class ProcessingSessionViewSet(viewsets.GenericViewSet):
    serializer_class = ProcessingSessionSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "snapshot", "detections", "detection_frame"):
            return [CanReadProcessing()]
        return [CanControlProcessing()]

    def get_queryset(self):
        qs = ProcessingSession.objects.select_related("config_snapshot").all()
        p = self.request.query_params
        if p.get("video"):
            qs = qs.filter(video_asset_id=p["video"])
        if p.get("camera"):
            qs = qs.filter(camera_id=p["camera"])
        if p.get("status"):
            qs = qs.filter(state=p["status"])
        return qs

    def _obj(self, pk) -> ProcessingSession:
        from django.shortcuts import get_object_or_404
        return get_object_or_404(ProcessingSession.objects.select_related("config_snapshot"), pk=pk)

    # ---- list / retrieve ----
    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response(ProcessingSessionSerializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(ProcessingSessionSerializer(self._obj(pk)).data)

    # ---- create ----
    def create(self, request):
        ser = CreateSessionSerializer(data=request.data)
        if not ser.is_valid():
            return _error("invalid_request", str(ser.errors), status.HTTP_400_BAD_REQUEST)
        try:
            session = create_session(
                video_id=ser.validated_data["video_id"],
                params=ser.to_params(), request=request, actor=request.user,
            )
        except ParamsError as exc:
            return _error(exc.code, str(exc), status.HTTP_400_BAD_REQUEST)
        except SessionError as exc:
            return _error(exc.code, str(exc), exc.status)
        return Response(ProcessingSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    # ---- commands (set requested_action; runtime performs transition) ----
    def _command(self, request, pk, fn, *, denied_msg="operation not allowed"):
        session = self._obj(pk)
        try:
            result = fn(session, request=request, actor=request.user)
        except SessionError as exc:
            return _error(exc.code, str(exc), exc.status)
        return Response(ProcessingSessionSerializer(result).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._command(request, pk, commands.request_cancel)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        return self._command(request, pk, commands.request_stop)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        return self._command(request, pk, commands.request_pause)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        return self._command(request, pk, commands.request_resume)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        session = self._obj(pk)
        try:
            new = retry_session(session, request=request, actor=request.user)
        except SessionError as exc:
            return _error(exc.code, str(exc), exc.status)
        return Response(ProcessingSessionSerializer(new).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def snapshot(self, request, pk=None):
        session = self._obj(pk)
        return Response(SnapshotMetadataSerializer(session.config_snapshot).data)

    # ---- detections (Phase 6, read-only) ----
    def _detections_qs(self, pk):
        qs = FrameDetectionBatch.objects.filter(session_id=pk)
        p = self.request.query_params
        frame = p.get("frame")
        if frame not in (None, ""):
            try:
                qs = qs.filter(source_frame_index=int(frame))
            except (TypeError, ValueError):
                qs = qs.none()
        for key, lookup in (("from_ts", "pts_seconds__gte"), ("to_ts", "pts_seconds__lte")):
            val = p.get(key)
            if val not in (None, ""):
                try:
                    qs = qs.filter(**{lookup: float(val)})
                except (TypeError, ValueError):
                    pass
        return qs.order_by("source_frame_index")

    @action(detail=True, methods=["get"])
    def detections(self, request, pk=None):
        """Paginated per-frame detections for a session. Filters: frame, from_ts,
        to_ts. Read gated to processing readers (viewer/incident_operator excluded)."""
        self._obj(pk)  # 404 if the session does not exist
        page = self.paginate_queryset(self._detections_qs(pk))
        return self.get_paginated_response(DetectionBatchSerializer(page, many=True).data)

    @action(detail=True, methods=["get"], url_path=r"detections/(?P<frame_index>\d+)")
    def detection_frame(self, request, pk=None, frame_index=None):
        """A single processed frame's detections by source frame index."""
        from django.shortcuts import get_object_or_404

        self._obj(pk)
        batch = get_object_or_404(
            FrameDetectionBatch, session_id=pk, source_frame_index=int(frame_index)
        )
        return Response(DetectionBatchSerializer(batch).data)


class RuntimeStatusView(APIView):
    """Non-gating CV-runtime availability (§33). Does NOT affect /api/readyz."""

    permission_classes = [CanReadProcessing]

    def get(self, request):
        from apps.processing.runtime.gpu import GPUManager
        from apps.processing.runtime.heartbeat import read_runtime_heartbeat_age
        from django.conf import settings

        age = read_runtime_heartbeat_age()
        available = age is not None and age <= settings.CV_HEARTBEAT_TTL_SECONDS
        gpu = GPUManager().status()
        return Response({
            "cv_runtime_available": available,
            "heartbeat_age_seconds": round(age, 1) if age is not None else None,
            "gpu": {
                "available": gpu.available, "mode": gpu.mode, "detector": gpu.detector,
                "devices": [
                    {"index": d.index, "name": d.name, "memory_total_mb": d.memory_total_mb,
                     "memory_free_mb": d.memory_free_mb, "driver_version": d.driver_version}
                    for d in gpu.devices
                ],
            },
        })

"""Video ingestion API (Phase 4 §13). No raw filesystem paths exposed."""
from __future__ import annotations

from django.db import transaction
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.audit.models import EventType
from apps.audit.services import record_audit
from apps.common.permissions import IsSystemAdmin
from apps.governance.models import ArtifactState, StoredArtifact
from apps.ingestion.ingest import IngestError, ingest_upload
from apps.ingestion.models import VideoAsset
from apps.ingestion.observability import record_upload_failure, record_upload_success
from apps.ingestion.permissions import CanManageVideo, CanReadVideo, CanUploadVideo
from apps.ingestion.serializers import VideoAssetSerializer, VideoMetadataSerializer
from apps.ingestion.storage import get_storage_backend
from apps.network.models import Camera


class VideoViewSet(viewsets.GenericViewSet):
    serializer_class = VideoAssetSerializer

    def get_permissions(self):
        if self.action == "create":
            return [CanUploadVideo()]
        if self.action in ("archive",):
            return [CanManageVideo()]
        if self.action == "destroy":
            return [IsSystemAdmin()]
        return [CanReadVideo()]

    def get_parsers(self):
        if getattr(self, "action", None) == "create":
            return [MultiPartParser(), FormParser()]
        return super().get_parsers()

    def get_queryset(self):
        qs = VideoAsset.objects.select_related("camera", "stored_artifact").all()
        p = self.request.query_params
        if p.get("camera"):
            qs = qs.filter(camera_id=p["camera"])
        if p.get("validation_status"):
            qs = qs.filter(validation_status=p["validation_status"])
        if p.get("source_type"):
            qs = qs.filter(source_type=p["source_type"])
        if p.get("is_active") is not None:
            qs = qs.filter(is_active=p["is_active"].lower() in ("1", "true", "yes"))
        return qs

    # ---- list / retrieve ----
    def list(self, request):
        page = self.paginate_queryset(self.get_queryset())
        ser = VideoAssetSerializer(page, many=True)
        return self.get_paginated_response(ser.data)

    def retrieve(self, request, pk=None):
        return Response(VideoAssetSerializer(self._obj(pk)).data)

    def _obj(self, pk) -> VideoAsset:
        from django.shortcuts import get_object_or_404

        return get_object_or_404(VideoAsset, pk=pk)

    # ---- upload ----
    def create(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response(
                {"error": {"code": "no_file", "message": "multipart 'file' is required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        camera = None
        camera_id = request.data.get("camera")
        if camera_id:
            camera = Camera.objects.filter(id=camera_id).first()
            if camera is None:
                return Response(
                    {"error": {"code": "invalid_camera", "message": "unknown camera"}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        try:
            asset = ingest_upload(upload, request=request, camera=camera)
        except IngestError as exc:
            record_upload_failure(exc.code)
            body = {"error": {"code": exc.code, "message": str(exc)}}
            if exc.existing_id:
                body["error"]["existing_id"] = exc.existing_id
            return Response(body, status=exc.status)
        record_upload_success(asset.size_bytes)
        return Response(VideoAssetSerializer(asset).data, status=status.HTTP_201_CREATED)

    # ---- metadata ----
    @action(detail=True, methods=["get"])
    def metadata(self, request, pk=None):
        return Response(VideoMetadataSerializer(self._obj(pk)).data)

    # ---- thumbnail (binary; bypasses the JSON envelope) ----
    @action(detail=True, methods=["get"])
    def thumbnail(self, request, pk=None):
        asset = self._obj(pk)
        if not asset.has_thumbnail or not asset.thumbnail_artifact_id:
            return Response(
                {"error": {"code": "no_thumbnail", "message": "no thumbnail available"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        backend = get_storage_backend()
        key = asset.thumbnail_artifact.path
        if not backend.exists(key):
            return Response(
                {"error": {"code": "file_missing", "message": "thumbnail file missing"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return FileResponse(backend.open(key), content_type="image/jpeg")

    # ---- archive ----
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        asset = self._obj(pk)
        with transaction.atomic():
            asset.is_active = False
            asset.save(update_fields=["is_active", "updated_at"])
            record_audit(
                EventType.VIDEO_ARCHIVED, action="archive_video", request=request,
                target_type="VideoAsset", target_id=asset.id, metadata={"archived": True},
            )
        return Response(VideoAssetSerializer(asset).data)

    # ---- hard delete (system_admin) ----
    def destroy(self, request, pk=None):
        asset = self._obj(pk)
        backend = get_storage_backend()
        keys = [asset.storage_key]
        artifact_ids = [asset.stored_artifact_id]
        if asset.thumbnail_artifact_id:
            keys.append(asset.thumbnail_artifact.path)
            artifact_ids.append(asset.thumbnail_artifact_id)
        target_id = asset.id
        checksum = asset.checksum_sha256[:12]

        def _delete_files():
            for k in keys:
                try:
                    backend.delete(k)
                except Exception:
                    # Leave a marker for the orphan sweep rather than failing the request.
                    StoredArtifact.objects.filter(path=k).update(state=ArtifactState.ORPHANED)

        with transaction.atomic():
            asset.delete()
            StoredArtifact.objects.filter(id__in=[a for a in artifact_ids if a]).delete()
            record_audit(
                EventType.VIDEO_DELETED, action="delete_video", request=request,
                target_type="VideoAsset", target_id=target_id, metadata={"checksum": checksum},
            )
            transaction.on_commit(_delete_files)
        return Response(status=status.HTTP_204_NO_CONTENT)

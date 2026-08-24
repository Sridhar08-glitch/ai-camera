"""Video ingestion routes under /api/v1/videos/."""
from django.urls import path

from apps.ingestion.views import VideoViewSet

_list = VideoViewSet.as_view({"get": "list", "post": "create"})
_detail = VideoViewSet.as_view({"get": "retrieve", "delete": "destroy"})
_metadata = VideoViewSet.as_view({"get": "metadata"})
_thumbnail = VideoViewSet.as_view({"get": "thumbnail"})
_archive = VideoViewSet.as_view({"post": "archive"})

urlpatterns = [
    path("videos", _list, name="video-list"),
    path("videos/<uuid:pk>", _detail, name="video-detail"),
    path("videos/<uuid:pk>/metadata", _metadata, name="video-metadata"),
    path("videos/<uuid:pk>/thumbnail", _thumbnail, name="video-thumbnail"),
    path("videos/<uuid:pk>/archive", _archive, name="video-archive"),
]

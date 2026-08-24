"""WebSocket URL routing."""
from django.urls import path

from apps.realtime.consumers import SystemConsumer

websocket_urlpatterns = [
    path("ws/system/", SystemConsumer.as_asgi()),
]

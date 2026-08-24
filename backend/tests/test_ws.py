"""WebSocket foundation tests (Phase 1 §14)."""
from __future__ import annotations

import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.db import close_old_connections
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import Role, User
from apps.common.roles import RoleCode
from apps.realtime.auth import JWTAuthMiddleware
from apps.realtime.routing import websocket_urlpatterns

# The Phase 1 WS teardown warning was caused by DB connections opened on
# thread-sensitive executors and never closed:
#   1. app side  — JWT auth middleware user lookup (fixed in SystemConsumer.disconnect)
#   2. test side — the async user-creation helper below
# The fixture closes the test-side executor connection so the test database can be
# torn down cleanly. Both are real root-cause fixes, not suppression.
application = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


@pytest.fixture(autouse=True)
async def _close_test_executor_connections():
    yield
    await sync_to_async(close_old_connections, thread_sensitive=True)()


def _make_operator() -> User:
    role, _ = Role.objects.get_or_create(
        code=RoleCode.TRAFFIC_OPERATOR, defaults={"name": "Traffic Operator"}
    )
    return User.objects.create_user(
        email="ws-op@example.com", password="TrafficPass123!", role=role
    )


def _token(user: User) -> str:
    return str(RefreshToken.for_user(user).access_token)


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_authenticated_heartbeat_and_ping():
    token = await _acreate_user_and_token()
    communicator = WebsocketCommunicator(
        application, "/ws/system/", subprotocols=["access_token", token]
    )
    connected, _ = await communicator.connect()
    assert connected is True

    welcome = await communicator.receive_json_from(timeout=2)
    assert welcome["type"] == "welcome"
    assert welcome["role"] == "traffic_operator"

    await communicator.send_json_to({"type": "ping"})
    pong = await communicator.receive_json_from(timeout=2)
    assert pong["type"] == "pong"

    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_rejects_missing_token():
    communicator = WebsocketCommunicator(application, "/ws/system/")
    await communicator.connect()
    close = await communicator.receive_output(timeout=2)
    assert close["type"] == "websocket.close"
    assert close["code"] == 4401
    await communicator.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_ws_rejects_invalid_token():
    communicator = WebsocketCommunicator(
        application, "/ws/system/", subprotocols=["access_token", "garbage"]
    )
    await communicator.connect()
    close = await communicator.receive_output(timeout=2)
    assert close["type"] == "websocket.close"
    assert close["code"] == 4401
    await communicator.disconnect()


# --- helpers -------------------------------------------------------------
from channels.db import database_sync_to_async  # noqa: E402


@database_sync_to_async
def _acreate_user_and_token() -> str:
    return _token(_make_operator())

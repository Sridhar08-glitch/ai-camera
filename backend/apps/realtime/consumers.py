"""
System heartbeat WebSocket consumer (Phase 1 §14).

Proves the authenticated real-time transport end-to-end: JWT auth at connect,
Redis channel layer, periodic server heartbeat, and ping/pong. Carries NO
traffic/business data (that arrives in later phases).
"""
from __future__ import annotations

import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

WS_CLOSE_UNAUTHENTICATED = 4401


class SystemConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            # Accept-then-close is required so browsers surface the close code.
            await self.accept(subprotocol=self._chosen_subprotocol())
            await self.close(code=WS_CLOSE_UNAUTHENTICATED)
            return

        await self.accept(subprotocol=self._chosen_subprotocol())
        await self.send_json(
            {
                "type": "welcome",
                "user_id": str(user.id),
                "role": user.role_code,
                "ts": self._now(),
            }
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, code):
        task = getattr(self, "_heartbeat_task", None)
        if task:
            task.cancel()
        # Release the DB connection opened on this context's thread-sensitive
        # executor by the JWT auth middleware (user lookup). Without this the
        # connection lingers, blocking test-database teardown and leaking a
        # connection per closed socket in production.
        await database_sync_to_async(close_old_connections)()

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong", "ts": self._now()})
        else:
            await self.send_json(
                {"type": "error", "message": "unknown message type"}
            )

    async def _heartbeat_loop(self):
        interval = settings.WS_HEARTBEAT_SECONDS
        try:
            while True:
                await asyncio.sleep(interval)
                await self.send_json({"type": "heartbeat", "ts": self._now()})
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            pass

    def _chosen_subprotocol(self) -> str | None:
        protocols = self.scope.get("subprotocols") or []
        return protocols[0] if protocols else None

    @staticmethod
    def _now() -> str:
        return timezone.now().isoformat()

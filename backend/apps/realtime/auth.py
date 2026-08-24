"""
WebSocket JWT authentication middleware for Channels (Phase 1 §14).

Uses the SAME short-lived access token as REST (clarification #2). Browsers
cannot set Authorization headers on WebSocket handshakes, so the access token is
accepted via the `Sec-WebSocket-Protocol` subprotocol (preferred) or a `token`
query parameter (fallback). The resolved user is placed in scope["user"]; the
consumer rejects anonymous connections.
"""
from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user(user_id):
    from apps.accounts.models import User

    try:
        return User.objects.select_related("role").get(id=user_id, is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


def _extract_token(scope) -> str | None:
    # Subprotocol form: client sends ["access_token", "<jwt>"].
    protocols = scope.get("subprotocols") or []
    if len(protocols) >= 2 and protocols[0] == "access_token":
        return protocols[1]
    # Query-param fallback: ?token=<jwt>
    query = parse_qs((scope.get("query_string") or b"").decode())
    token = query.get("token")
    return token[0] if token else None


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        token = _extract_token(scope)
        scope["user"] = AnonymousUser()
        scope["auth_error"] = None
        if token:
            try:
                access = AccessToken(token)
                scope["user"] = await _get_user(access["user_id"])
            except TokenError:
                scope["auth_error"] = "invalid_token"
            except KeyError:
                scope["auth_error"] = "invalid_token"
        return await super().__call__(scope, receive, send)

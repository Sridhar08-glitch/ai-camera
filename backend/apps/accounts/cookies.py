"""HttpOnly refresh-token cookie helpers (clarification #1)."""
from __future__ import annotations

from django.conf import settings
from rest_framework.response import Response


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    cfg = settings.REFRESH_COOKIE
    max_age = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
    response.set_cookie(
        key=cfg["NAME"],
        value=refresh_token,
        max_age=max_age,
        httponly=cfg["HTTPONLY"],
        secure=cfg["SECURE"],
        samesite=cfg["SAMESITE"],
        domain=cfg["DOMAIN"],
        path=cfg["PATH"],
    )


def clear_refresh_cookie(response: Response) -> None:
    cfg = settings.REFRESH_COOKIE
    response.delete_cookie(
        key=cfg["NAME"],
        path=cfg["PATH"],
        domain=cfg["DOMAIN"],
        samesite=cfg["SAMESITE"],
    )


def get_refresh_from_cookie(request) -> str | None:
    return request.COOKIES.get(settings.REFRESH_COOKIE["NAME"])

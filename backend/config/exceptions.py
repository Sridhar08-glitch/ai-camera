"""
Standard error envelope + DRF exception handler (Phase 1 §19).

Never hide exceptions or fake success. Unhandled 500s are logged with the
request id and stack, but internal details are not leaked in the response.
"""
from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exc
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_default_handler

from apps.common.request_context import get_request_id
from config.logging import get_logger

logger = get_logger("api.error")


def _code_for(exc: Exception, status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        406: "not_acceptable",
        415: "unsupported_media_type",
        429: "throttled",
    }
    if isinstance(exc, drf_exc.ValidationError):
        return "validation_error"
    return mapping.get(status_code, "error")


def error_envelope(*, code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return body


def standard_exception_handler(exc: Exception, context: dict) -> Response | None:
    # Normalize Django-native exceptions DRF does not handle by default.
    if isinstance(exc, Http404):
        exc = drf_exc.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exc.PermissionDenied()

    response = drf_default_handler(exc, context)

    if response is None:
        # Unhandled -> 500. Log with stack + request id; do not leak internals.
        logger.error(
            "unhandled_exception",
            exc_info=exc,
            path=_safe_path(context),
        )
        return Response(
            error_envelope(
                code="internal_error",
                message="An unexpected error occurred.",
            ),
            status=500,
        )

    code = _code_for(exc, response.status_code)
    detail = response.data
    message = _extract_message(detail)
    details = detail if isinstance(detail, (dict, list)) and code == "validation_error" else None

    response.data = error_envelope(code=code, message=message, details=details)["error"]
    response.data = {"error": response.data}
    return response


def _extract_message(detail: Any) -> str:
    if isinstance(detail, dict):
        if "detail" in detail:
            return str(detail["detail"])
        return "Request could not be processed."
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def _safe_path(context: dict) -> str:
    request = context.get("request")
    return getattr(request, "path", "") if request else ""

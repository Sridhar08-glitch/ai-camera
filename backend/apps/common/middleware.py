"""
Request-id correlation + structured access logging (Phase 1 §18).
"""
from __future__ import annotations

import time
import uuid

import structlog

from apps.common.request_context import get_request_id, set_request_id

logger = structlog.get_logger("http.access")

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
RESPONSE_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """Assign/propagate an X-Request-ID and bind it to the log context."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        set_request_id(request_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.request_id = request_id

        response = self.get_response(request)
        response[RESPONSE_HEADER] = request_id
        return response


class RequestLoggingMiddleware:
    """Emit one structured log line per request with timing + status."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        user = getattr(request, "user", None)
        user_id = str(user.id) if getattr(user, "is_authenticated", False) else None

        logger.info(
            "request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            request_id=get_request_id(),
        )
        return response

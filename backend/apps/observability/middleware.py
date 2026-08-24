"""Request metrics middleware (Phase 2 §14). Increments in-memory counters only."""
from __future__ import annotations

import time

from apps.observability.collectors import incr, observe


def _status_class(status: int) -> str:
    return f"{status // 100}xx"


class MetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = (time.perf_counter() - start) * 1000
        status_class = _status_class(response.status_code)
        method = request.method

        incr("http_requests_total", {"method": method, "status_class": status_class})
        observe("http_request_latency_ms", duration_ms, {"method": method})
        if response.status_code >= 400:
            incr("http_errors_total", {"status_class": status_class})
        return response

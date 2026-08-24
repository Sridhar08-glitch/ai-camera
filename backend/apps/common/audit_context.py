"""
Helpers to capture actor/IP/request-id context for audit events (Phase 2 §12).

Kept in `common` so no feature app depends on another. Works for both HTTP
requests (DRF `request`) and is safe when called with `None`.
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.common.request_context import get_request_id


@dataclass
class AuditContext:
    actor: object | None
    actor_email: str
    actor_role: str
    request_id: str
    ip_address: str | None
    source: str


def _client_ip(request) -> str | None:
    if request is None:
        return None
    # Respect a single trusted proxy hop; do not trust arbitrary XFF in general.
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def build_context(request=None, actor=None, source: str = "django") -> AuditContext:
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        actor = user if getattr(user, "is_authenticated", False) else None

    actor_email = getattr(actor, "email", "") or ""
    actor_role = ""
    role = getattr(actor, "role", None)
    if role is not None:
        actor_role = getattr(role, "code", "") or ""

    return AuditContext(
        actor=actor,
        actor_email=actor_email,
        actor_role=actor_role,
        request_id=get_request_id(),
        ip_address=_client_ip(request),
        source=source,
    )

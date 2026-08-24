"""Standard success envelope + JSON renderer (Phase 1 §19)."""
from __future__ import annotations

from typing import Any

from rest_framework.renderers import JSONRenderer


def data_envelope(payload: Any, meta: dict | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"data": payload}
    if meta is not None:
        body["meta"] = meta
    return body


class EnvelopeJSONRenderer(JSONRenderer):
    """
    Wrap successful payloads in {"data": ...} unless already enveloped.

    Leaves alone: error envelopes ({"error": ...}), already-enveloped
    payloads ({"data": ...}), and empty bodies (e.g. 204).
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is not None and isinstance(data, dict):
            # Already an error envelope (error is always a dict) or already wrapped.
            already_error = isinstance(data.get("error"), dict)
            already_wrapped = "data" in data
            if already_error or already_wrapped:
                return super().render(data, accepted_media_type, renderer_context)
        if data is None:
            return super().render(data, accepted_media_type, renderer_context)
        return super().render({"data": data}, accepted_media_type, renderer_context)

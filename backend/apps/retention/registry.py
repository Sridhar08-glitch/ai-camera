"""
Retention handler registry (Phase 2 §19).

Apps register a RetentionHandler per data category. The execution engine only ever
acts on categories that have a registered handler — an unknown/absent handler is
skipped safely (never a blind delete). This lets future apps plug in retention for
their own data without editing the engine.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RetentionResult:
    scanned: int
    deleted: int


class RetentionHandler:
    """Base handler. Subclass, set `category`, implement `count` and `purge`."""

    category: str = ""

    def count(self, cutoff) -> int:
        raise NotImplementedError

    def purge(self, cutoff, *, batch_size: int, max_deletes: int, dry_run: bool) -> RetentionResult:
        raise NotImplementedError


_REGISTRY: dict[str, RetentionHandler] = {}


def register(handler: RetentionHandler) -> RetentionHandler:
    if not handler.category:
        raise ValueError("RetentionHandler must define a category.")
    _REGISTRY[handler.category] = handler
    return handler


def get_handler(category: str) -> RetentionHandler | None:
    return _REGISTRY.get(category)


def registered_categories() -> list[str]:
    return sorted(_REGISTRY.keys())

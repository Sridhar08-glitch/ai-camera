# ADR-011 — Redis on Windows (D3 resolution)

**Status:** Accepted (Phase 1)

## Decision
Use **Memurai** (native Windows, Redis-protocol compatible) as the local
development Redis. It was already installed and running as a Windows service on
`127.0.0.1:6379` and passed live smoke tests (PING, SET/GET, pub/sub via the
Channels layer and Celery broker).

## Context
- D3 (approved) required the most reliable **free** native Redis-compatible
  option, else WSL2 Redis, with **no paid dependency**.
- Memurai Developer Edition is free for development use and native to Windows,
  so no WSL2 fallback was needed. WSL2 Ubuntu is present as a fallback if Memurai
  becomes unavailable.
- Redis DB indexes used: `/0` cache + channel layer + heartbeat, `/1` Celery
  broker, `/2` Celery result backend.

## Production note
Production/edge Redis will run on Linux; nothing here is Memurai-specific
(standard Redis protocol only), so there is no lock-in.

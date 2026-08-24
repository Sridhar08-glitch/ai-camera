# ADR-002 — Three-runtime split (foundation portion)

**Status:** Accepted (Phase 1 establishes the boundary; CV runtime arrives Phase 5)

## Decision
The platform runs as a modular monolith across separate processes:
- **Django/DRF/Channels** (control plane) — auth, config, REST, WebSocket relay.
- **Celery worker + beat** (short/medium jobs) — Phase 1 ships a `ping` task and a
  periodic `write_worker_heartbeat` task.
- **CV Processing Runtime** (data plane) — reserved; NOT built in Phase 1.

Inter-runtime communication uses PostgreSQL (durable state) and Redis
(broker, channel layer, worker heartbeat). Django never loads GPU/CV code.

## Phase 1 specifics
- On Windows, the Celery worker uses `--pool=solo` and **beat runs as a separate
  process** (embedded `-B` is unsupported on Windows).
- Worker liveness is observed by `/readyz` through a cached Redis heartbeat key
  written by beat — no task is dispatched per readiness request (clarification #3).

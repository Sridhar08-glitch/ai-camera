# ADR-025 — CV Runtime Boundary

**Status:** Accepted (Phase 5)

## Context
Frozen ADR-002 mandates a three-runtime split and explicitly rejected running CV
work inside Celery ("Celery = short/medium jobs only"). Phase 5 builds the CV
runtime skeleton (no AI yet) that will later own GPU/model loading.

## Decision
A **standalone CV runtime process**, launched via
`python manage.py run_cv_runtime` (dev script `scripts/dev_cv_runtime.ps1`):
- Loads Django settings/ORM for durable state but **serves no HTTP**.
- Claims the oldest `QUEUED` session atomically from PostgreSQL
  (`SELECT … FOR UPDATE SKIP LOCKED`) under the concurrency cap, transitioning it
  `QUEUED→INITIALIZING` with its `runtime_id`.
- Runs the linear pipeline (decode → sample → FrameProcessor → bounded progress +
  heartbeat → command check), the **single writer** of session state.
- Posts liveness to Redis (`cv:session:{id}:heartbeat`, `cv:runtime:heartbeat`,
  TTL) and mirrors it to the durable `last_heartbeat_at` column.
- **Communicates only via PostgreSQL (authoritative) + Redis (fast path).**

**Celery keeps only the watchdog** (`reconcile_stale_sessions`, beat every 60 s) —
no CV/decoding in Celery. Django remains the control plane (auth, config, session
control API, WebSocket relay).

**Windows lifecycle:** SIGINT/SIGBREAK/SIGTERM set a shutdown flag; the loop exits
at the next frame boundary, closes the PyAV container in `finally`, releases the GPU
reservation and heartbeat, and exits 0. A crash leaves a safe non-terminal row that
the watchdog fails; there is no OS lock file to clean up.

## Alternatives rejected
- **Celery queue/worker for CV** — violates frozen ADR-002 and would force a rewrite
  once GPU model ownership (Phase 6) needs a long-lived single-owner process.
- **Hybrid Celery-dispatch** — adds a hop with no benefit on one laptop; Django
  already writes QUEUED and the runtime polls/claims directly.

## Consequences
The boundary (Postgres + Redis only) lets the runtime move hosts later unchanged.
Readiness of the API does not depend on the runtime (ADR: `/api/readyz` unchanged; a
separate non-gating `/api/v1/processing/runtime-status` reports runtime + GPU).

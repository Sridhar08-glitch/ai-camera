# ADR-024 — Processing Session Architecture & State Machine

**Status:** Accepted (Phase 5)

## Context
Phase 5 introduces the durable `ProcessingSession` that drives a video through a
no-AI processing lifecycle. Phase 0 §13 froze a single-writer state machine with
START/PAUSE/RESUME/STOP/CANCEL and heartbeats; the concrete ADR ("ADR-003" in the
Phase 0 sketch) is realized here under the actual on-disk ADR numbering.

## Decision
`ProcessingSession` (UUID PK) with states:
```
CREATED → QUEUED → INITIALIZING → RUNNING
                                   RUNNING ⇄ PAUSING → PAUSED → RESUMING → RUNNING
                                   RUNNING → COMPLETING → COMPLETED
Terminal: FAILED · CANCELLED · STOPPED
```

- **Single writer = CV runtime.** Django writes only `CREATED→QUEUED` and a
  pre-pickup `→CANCELLED`; it expresses all other intent via a `requested_action`
  column (PAUSE/RESUME/STOP/CANCEL). The runtime performs every other transition at
  a safe frame boundary. This is the frozen anti-race rule.
- **One authoritative service** `apps.processing.services.state.transition()` is the
  only code that writes `state`. It validates the transition table
  (`apps.processing.states.ALLOWED_TRANSITIONS`), stamps the entry timestamp, writes
  an `AuditEvent`, emits a structured log, and records finish metrics. Same-state
  calls are idempotent no-ops; forbidden transitions raise `InvalidTransition`.
- **DB guardrails:** a `CheckConstraint` restricts `state` to the enum; a partial
  unique index (`uq_processing_active_per_video`) forbids two non-terminal sessions
  for one video.
- **API cannot set state** — only command endpoints that set `requested_action`.
- **Retry** creates a NEW session linked via `retry_of` (original stays immutable);
  never resets a terminal session (see ADR handling in §Retry).
- **Concurrency** is bounded by `CV_MAX_CONCURRENT_SESSIONS` (default 1 on 8 GB
  VRAM), enforced in the runtime claim (`FOR UPDATE SKIP LOCKED`).

## Consequences
Phase 6 detection plugs into the same lifecycle without state-machine changes. The
single-writer + `requested_action` split prevents Django/runtime races on `state`.
Terminal immutability preserves execution history for audit.

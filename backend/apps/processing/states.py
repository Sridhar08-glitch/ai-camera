"""
Processing session state machine (Phase 5 / ADR-024).

Frozen PHASE_0_ARCHITECTURE.md §13: single-writer = CV runtime; Django only sets
QUEUED and pre-pickup CANCELLED, and expresses intent via `requested_action`.
This module is the authoritative definition of states, transitions, and sampling
modes. All state writes flow through apps.processing.services.state.transition().
"""
from __future__ import annotations

from django.db import models


class ProcessingState(models.TextChoices):
    CREATED = "created", "Created"
    QUEUED = "queued", "Queued"
    INITIALIZING = "initializing", "Initializing"
    RUNNING = "running", "Running"
    PAUSING = "pausing", "Pausing"
    PAUSED = "paused", "Paused"
    RESUMING = "resuming", "Resuming"
    COMPLETING = "completing", "Completing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"
    STOPPED = "stopped", "Stopped"


class RequestedAction(models.TextChoices):
    NONE = "none", "None"
    PAUSE = "pause", "Pause"
    RESUME = "resume", "Resume"
    STOP = "stop", "Stop"
    CANCEL = "cancel", "Cancel"


class SamplingMode(models.TextChoices):
    EVERY_FRAME = "every_frame", "Every frame"
    EVERY_N = "every_n", "Every Nth frame"
    TARGET_FPS = "target_fps", "Target FPS"


# Terminal states have no outgoing transitions.
TERMINAL_STATES: frozenset[str] = frozenset({
    ProcessingState.COMPLETED,
    ProcessingState.FAILED,
    ProcessingState.CANCELLED,
    ProcessingState.STOPPED,
})

# Non-terminal states: a video bound to any of these is protected from retention
# and blocks a duplicate active session (§25/§26).
NON_TERMINAL_STATES: frozenset[str] = frozenset(
    s for s, _ in ProcessingState.choices
) - TERMINAL_STATES

# States in which the CV runtime is actively holding the session (used by the
# stale-session watchdog, §23).
RUNTIME_ACTIVE_STATES: frozenset[str] = frozenset({
    ProcessingState.INITIALIZING,
    ProcessingState.RUNNING,
    ProcessingState.PAUSING,
    ProcessingState.PAUSED,
    ProcessingState.RESUMING,
    ProcessingState.COMPLETING,
})

# Authoritative transition table (from -> allowed to). Anything not listed is a
# forbidden transition and is rejected + logged by the transition service.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ProcessingState.CREATED: frozenset({ProcessingState.QUEUED, ProcessingState.CANCELLED}),
    ProcessingState.QUEUED: frozenset({ProcessingState.INITIALIZING, ProcessingState.CANCELLED}),
    ProcessingState.INITIALIZING: frozenset({
        ProcessingState.RUNNING, ProcessingState.FAILED, ProcessingState.CANCELLED,
    }),
    ProcessingState.RUNNING: frozenset({
        ProcessingState.COMPLETING, ProcessingState.PAUSING, ProcessingState.STOPPED,
        ProcessingState.CANCELLED, ProcessingState.FAILED,
    }),
    ProcessingState.PAUSING: frozenset({
        ProcessingState.PAUSED, ProcessingState.FAILED, ProcessingState.CANCELLED,
    }),
    ProcessingState.PAUSED: frozenset({
        ProcessingState.RESUMING, ProcessingState.STOPPED,
        ProcessingState.CANCELLED, ProcessingState.FAILED,
    }),
    ProcessingState.RESUMING: frozenset({
        ProcessingState.RUNNING, ProcessingState.FAILED, ProcessingState.CANCELLED,
    }),
    ProcessingState.COMPLETING: frozenset({ProcessingState.COMPLETED, ProcessingState.FAILED}),
    ProcessingState.COMPLETED: frozenset(),
    ProcessingState.FAILED: frozenset(),
    ProcessingState.CANCELLED: frozenset(),
    ProcessingState.STOPPED: frozenset(),
}

# Timestamp column stamped when a state is first entered (§5).
STATE_TIMESTAMP_FIELD: dict[str, str] = {
    ProcessingState.QUEUED: "queued_at",
    ProcessingState.INITIALIZING: "started_at",
    ProcessingState.PAUSED: "paused_at",
    ProcessingState.COMPLETED: "completed_at",
    ProcessingState.FAILED: "failed_at",
    ProcessingState.CANCELLED: "cancelled_at",
    ProcessingState.STOPPED: "stopped_at",
}


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def can_transition(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())

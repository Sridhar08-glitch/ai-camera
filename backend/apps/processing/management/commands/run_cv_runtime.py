"""
Standalone CV runtime process (Phase 5 §10/§34 / ADR-025).

Separate from Django request handling and general Celery workers. Owns decoding
and (future) GPU/model loading. Claims QUEUED sessions from PostgreSQL, runs the
pipeline, posts heartbeats. Graceful Ctrl+C: finish the current frame, leave the
session in a safe state, release resources, exit.

    python manage.py run_cv_runtime [--once] [--runtime-id ID]
"""
from __future__ import annotations

import signal
import socket
import time
import uuid

import structlog
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.processing.runtime import heartbeat
from apps.processing.runtime.gpu import GPUManager

logger = structlog.get_logger("processing")


class Command(BaseCommand):
    help = "Run the standalone CV processing runtime (Phase 5, no AI)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true",
                            help="Process one claimed session then exit (for scripts/tests).")
        parser.add_argument("--runtime-id", default="",
                            help="Override the runtime identity (default: host:pid:uuid).")

    def handle(self, *args, **opts):
        from apps.common.redis_client import get_redis
        from apps.processing.services.claim import claim_next
        from apps.processing.runtime.pipeline import run_session

        runtime_id = opts["runtime_id"] or f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
        self._stopping = False

        def _signal(signum, frame):
            self.stdout.write(self.style.WARNING(f"\nshutdown signal {signum}; finishing current frame..."))
            self._stopping = True

        signal.signal(signal.SIGINT, _signal)
        if hasattr(signal, "SIGBREAK"):  # Windows Ctrl+Break
            signal.signal(signal.SIGBREAK, _signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _signal)

        redis_client = None
        try:
            redis_client = get_redis()
        except Exception:  # runtime still works; heartbeats/commands degrade
            pass

        gpu = GPUManager(redis_client=redis_client)
        status = gpu.status()
        self.stdout.write(self.style.SUCCESS(
            f"CV runtime {runtime_id} up | device mode: {status.mode} "
            f"| gpus: {[d.name for d in status.devices] or 'none (cpu)'}"
        ))

        def shutdown():
            return self._stopping

        while not self._stopping:
            heartbeat.write_runtime_heartbeat(runtime_id, redis_client=redis_client)
            try:
                session = claim_next(runtime_id)
            except Exception as exc:  # DB blip — back off, keep runtime alive
                logger.error("cv_runtime_claim_error", error=str(exc)[:200])
                session = None
                time.sleep(settings.CV_RUNTIME_POLL_SECONDS)
                continue

            if session is None:
                if opts["once"]:
                    self.stdout.write("no queued session; --once exiting.")
                    break
                time.sleep(settings.CV_RUNTIME_POLL_SECONDS)
                continue

            self.stdout.write(f"claimed session {session.id} ({session.video_asset_id})")
            terminal = run_session(session, gpu_manager=gpu, shutdown=shutdown,
                                   redis_client=redis_client)
            self.stdout.write(self.style.SUCCESS(f"session {session.id} -> {terminal}"))
            if opts["once"]:
                break

        self.stdout.write(self.style.WARNING(f"CV runtime {runtime_id} stopped."))

# ADR-017 — Metrics architecture

**Status:** Accepted (Phase 2)

## Decision
Lightweight, local-first operational metrics stored as **pre-aggregated, sampled**
rows in `observability.SystemMetric`. No external observability stack
(no Prometheus/Grafana/ELK/OpenTelemetry).

## Rules
- **No per-request PostgreSQL writes.** In-memory counters/timers accumulate
  request count/latency/errors (middleware) and Celery task duration/failures
  (signals). A Celery beat task flushes aggregates (count, sum, min, max) per
  bucket into `SystemMetric`, then resets.
- **No unbounded cardinality.** `labels` (JSONB) is validated against a per-metric
  allowlist; unknown labels are rejected. Metric `name` comes from a registered set.
- **No per-second permanent hardware writes.** CPU/RAM/GPU/VRAM/FPS metrics are
  reserved as future interfaces, NOT implemented in Phase 2.
- **Bounded retention.** `RetentionPolicy(category=SYSTEM_METRIC)`, default short
  (30 days), configurable.

## Separation of concerns (never one generic table)
Structured logs (structlog) · security audit (`audit_event`) · operational metrics
(`system_metric`) · performance measurements (future CV) · business analytics
(future traffic) are distinct stores with distinct lifecycles.

## PostgreSQL vs ephemeral
Aggregated operational metrics → PostgreSQL (retained). Raw high-frequency samples
→ ephemeral in-memory (reset on flush). `SystemMetric` stays unpartitioned in
Phase 2 (bounded by sampling + retention); partition later only on measured need.

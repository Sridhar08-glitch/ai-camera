# ADR-018 — Time-series & partitioning strategy

**Status:** Accepted (Phase 2) · Confirms D2 (plain PostgreSQL, TimescaleDB deferred)

## Decision
Use plain PostgreSQL with **native declarative RANGE partitioning by time**, applied
only to genuinely high-volume tables and only when volume warrants it. Retention
integrates by **dropping whole partitions** rather than row-by-row deletes.

## Future high-volume tables (not created in Phase 2)
| Table (future phase) | Partition key | Interval | Introduce when |
|---|---|---|---|
| TrafficMeasurement (P6/P8) | `bucket_start`/`ts` | daily or weekly | projected > ~10–50M rows |
| Detection metadata (P4/P5) | `created_at` | daily | high-volume raw metadata |
| Track metadata (P5/P6) | `created_at` | weekly | medium volume |
| Processing metrics (P5+) | `bucket_start` | weekly | sustained streaming |

## Phase 2 tables
- `SystemMetric`: **unpartitioned**. Bounded by sampling + short retention; revisit
  only if measured volume grows.
- `AuditEvent`, `RetentionRun`, governance tables: unpartitioned (low volume).

## Why not TimescaleDB now
Native partitioning + our aggregation/retention covers laptop-scale. TimescaleDB
adds an extension dependency with no current measured benefit. Revisit strictly on
measured need (per D2). No future traffic tables or premature partitioning created
in Phase 2.

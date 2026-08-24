# PHASE 2 — OBSERVABILITY, GOVERNANCE & DATA RETENTION — IMPLEMENTATION PLAN

**Project:** AI Traffic Intelligence & Management Platform
**Phase:** 2 — Platform Foundations (observability, audit, governance, retention)
**Depends on:** Phase 0 (frozen), Phase 1 (COMPLETE WITH KNOWN LIMITATIONS)
**Status:** READY FOR REVIEW — planning only; no code, migrations, deps, or edits to existing files.

---

## 1. Current State Verified

Inspected the live repo (not just the report): apps, models, migrations, settings, tests, ADRs, `.env`, and source.

**Confirmed accurate vs. PHASE_1_VERIFICATION_REPORT.md:**
- Django apps: `common`, `accounts`, `health`, `realtime` (exactly four). ✅
- Migrations: only `accounts/0001_initial` + `accounts/0002_seed_roles`. `common`/`health`/`realtime` have no models/migrations. ✅
- Models: `accounts.Role`, `accounts.User`; abstract `common.UUIDModel`/`TimeStampedModel`/`UUIDTimeStampedModel`. ✅
- Settings: `INSTALLED_APPS` lists the four apps; `RequestIDMiddleware` + `RequestLoggingMiddleware`; `EnvelopeJSONRenderer`; `StandardPagination`; SimpleJWT rotation+blacklist; `REFRESH_COOKIE`; `CHANNEL_LAYERS` (Redis); Celery on Redis DBs 1/2; `CELERY_HEARTBEAT_KEY`/`TTL`. ✅
- ADRs present: 001, 002, 011, 013 (gaps 003–010, 012 intentional). ✅
- DB: `DATABASE_URL=postgresql://postgres:holora@127.0.0.1:5432/aitraffic` — **still the `postgres` superuser** (Phase 1 debt confirmed). ✅
- Retention/metrics/audit/model-governance: **none exist** — greenfield for Phase 2. ✅

**Discrepancy found (reported per instruction, not silently accepted):**
- The Phase 1 report states "Phase 1 logs auth events but does not persist an audit table." **Reality:** there is **no dedicated auth-event logging** in `accounts` (grep of `apps/accounts/` for any logger/structlog = none). Auth requests are captured only by the generic `RequestLoggingMiddleware` (method/path/status/duration/user_id/request_id) — which does log login/logout HTTP calls, but there is no semantic "login_success/login_failure" event. **Impact:** Phase 2's audit foundation must *introduce* auth-event emission, not merely persist an existing stream. No functional defect; a reporting overstatement.

**No other discrepancies.** No serious Phase 1 defects discovered. The WS teardown warning is analyzed in §4.2.

---

## 2. Phase 2 Objectives

Build reusable, laptop-first platform foundations that later phases depend on:
1. **Least-privilege DB role** (resolve Phase 1 debt 3.1).
2. **Durable, immutable `AuditEvent`** system with safe emission semantics.
3. **Lightweight observability**: operational **metrics** foundation (bounded, sampled) distinct from logs/audit/analytics.
4. **AI model governance** (`AIModel`/`AIModelVersion`/`ModelArtifact`/`ModelEvaluation`) — metadata + artifact references, no weights in DB, no inference.
5. **Algorithm version governance** (`AlgorithmDefinition`/`AlgorithmVersion`) for deterministic components.
6. **Retention policy engine** (`RetentionPolicy`) + **execution engine** (pluggable `RetentionHandler`, dry-run, bounded, audited).
7. **Storage governance seed** (`StoredArtifact` registry — minimal) + **data-classification vocabulary**.
8. **Celery schedules** for metric collection + retention evaluation.
9. **Admin-only APIs + minimal admin UI** for audit/metrics/retention/registry.
10. Fix the WS test-teardown warning at root cause; add a practical clean-setup reproducibility check.

---

## 3. Explicit Non-Goals (Phase 2)

Excluded (owned by later phases): traffic-network/camera models, video upload/processing, CV runtime, GPU management, detection/tracking/lane/speed/congestion/queue/incident logic, SUMO, signal optimization, prediction, digital twin, Traffic Operations Center, maps/camera grids/traffic charts. No Prometheus/Grafana/ELK/OpenTelemetry. No storing model weights or media blobs in PostgreSQL. No real inference or evaluation runs. No new frontend beyond admin foundation pages.

---

## 4. Phase 1 Technical Debt Resolution

### 4.1 Least-Privilege PostgreSQL Application User (debt 3.1)

**Recommendation: Option A — a single dedicated non-superuser role `aitraffic_app`** that owns the app tables and runs both migrations and runtime. Rationale (laptop-first, ADR-014): a separate migration-owner vs runtime role adds operational complexity (two credentials, GRANT choreography, ownership handoffs) with little security benefit on a single-dev local box. A single owner role that is **not** a superuser already removes the real risk (cluster-wide superuser).

**Design (to be applied in implementation, not now):**
- Create role `aitraffic_app LOGIN PASSWORD <env>` — **NOSUPERUSER NOCREATEDB NOCREATEROLE**.
- Grant: `CONNECT` on `aitraffic`; `USAGE`+`CREATE` on schema `public` (and later on `config/operational/analytical/ai` when used); ownership (or full DML+DDL) of application tables so Django migrations succeed.
- Provide `scripts/create_app_role.ps1` (idempotent) run **once by the developer** with the superuser; then `.env` `DATABASE_URL` switches to `aitraffic_app`. **Credentials are not changed during planning.**
- Django `default` connection uses `aitraffic_app`. The `postgres` superuser is used only for the one-time role/schema bootstrap.
- Test DB creation: `aitraffic_app` needs `CREATEDB` **or** pytest uses `--reuse-db`/a pre-created `test_aitraffic` owned by the role. **Decision (ADR-014):** grant `CREATEDB` to `aitraffic_app` (narrow, local-only) so `pytest` and `migrate` work unchanged — simplest secure path for laptop dev. Documented trade-off: `CREATEDB` is a low-risk privilege far below superuser.
- Acceptance: app boots, migrates, and full suite passes as `aitraffic_app`; a negative test asserts the role is **not** superuser (`SELECT rolsuper FROM pg_roles`).

### 4.2 WebSocket Test Teardown Warning (debt 3.2)

**Root cause (confirmed by inspection):** `tests/test_ws.py` uses `@pytest.mark.django_db(transaction=True)`. The consumer path calls `JWTAuthMiddleware._get_user` via `database_sync_to_async`, which runs on the async thread-pool executor and opens a Django DB connection **on that worker thread**. `WebsocketCommunicator.disconnect()` closes the socket but does **not** close that thread's DB connection. At teardown, pytest-django tries to drop `test_aitraffic` while that connection is still open → `OperationalError: database "test_aitraffic" is being accessed by other users`. It is a lingering async connection, not incomplete socket cleanup.

**Fix (planned, not a suppression):**
- Add a small async test finalizer/fixture that calls `close_old_connections()` (sync-wrapped) after each WS test, and/or close connections inside the consumer `disconnect()` for the test path. Preferred: a `conftest` fixture wrapping WS tests that, after `communicator.disconnect()`, runs `await sync_to_async(close_old_connections)()` and awaits executor drain.
- Validate: run `test_ws.py` repeatedly; the teardown `OperationalError` must no longer appear (assert clean teardown, e.g. via `-W error` scoped to that message or capturing warnings).
- If the residual connection proves to be Channels-internal and unclosable from test code, document the exact mechanism and use `pytest --reuse-db` for WS tests as the sanctioned mitigation — but only after demonstrating the root cause fix was attempted first.

### 4.3 README Clean-Setup Reproducibility (debt 3.3, AC-14)

**Non-destructive strategy** (does not touch the working env):
- **Backend:** create a throwaway venv in a temp dir (`%TEMP%\p2venv`), `pip install -r requirements/dev.txt` from clean, and run `python -c "import django, channels, celery, psycopg, structlog, rest_framework_simplejwt"` + `manage.py check`. Detects missing/implicit deps.
- **DB:** create a temporary throwaway database `aitraffic_repro` (owned by the app role), run `migrate` + role seed, assert 6 roles, then **drop it**. Never touches `aitraffic`.
- **Frontend:** `corepack pnpm install --frozen-lockfile` into a temp clone of `frontend/` (or `pnpm install --ignore-scripts` in a copied dir) + `pnpm run build`. Confirms the lockfile is sufficient.
- Capture any hidden assumptions (global tools, env vars) in the verification report. Provide `scripts/verify_clean_setup.ps1` implementing the above with automatic teardown.

---

## 5. Final Phase 2 Scope

Four new Django apps (all reusable, no traffic domain):
- **`audit`** — `AuditEvent`, emission service, admin API.
- **`observability`** — `SystemMetric`, collectors, metric API/summary.
- **`governance`** — `AIModel`, `AIModelVersion`, `ModelArtifact`, `ModelEvaluation`, `AlgorithmDefinition`, `AlgorithmVersion`, `StoredArtifact`.
- **`retention`** — `DataCategory` vocabulary, `RetentionPolicy`, `RetentionRun`, `RetentionHandler` registry + handlers for categories that exist now (audit, metrics).

Plus: least-privilege role, WS teardown fix, clean-setup script, Celery schedules, admin APIs + minimal admin UI, ADRs 014–018, full tests + regression.

---

## 6. Architecture Components

| Component | Phase 2 build | Deferred |
|---|---|---|
| Audit | Model + `record_audit()` service + emitters wired into accounts/retention/governance + API | Session/incident audit (later phases emit via same service) |
| Metrics | `SystemMetric` + collectors (request, task, health) + Celery sampler + retention | FPS/GPU/VRAM (interfaces only) |
| Model governance | Registry models + artifact refs + evaluation records + API | Real inference/eval |
| Algorithm governance | Definition/version + config hash + immutability | Actual algorithm code (later phases) |
| Retention | Policy + run + handler registry + dry-run + bounded delete | Handlers for future data (video/tracks) registered later |
| Storage governance | Minimal `StoredArtifact` registry (path, category, checksum, size) | Media engine (Phase 4) |
| DB security | `aitraffic_app` least-privilege role | Separate migration role (not needed) |

Registry pattern: `RetentionHandler` and `MetricCollector` are **pluggable** — future apps register handlers/collectors without editing Phase 2 code (Django app-ready hooks).

---

## 7. Repository Changes

New (nothing existing modified except additive settings/URLs at implementation time):
```
backend/apps/audit/{__init__,apps,models,services,serializers,views,urls,permissions}.py + migrations/
backend/apps/observability/{__init__,apps,models,collectors,tasks,serializers,views,urls}.py + migrations/
backend/apps/governance/{__init__,apps,models,serializers,views,urls,permissions,checksums}.py + migrations/
backend/apps/retention/{__init__,apps,models,registry,handlers,tasks,serializers,views,urls}.py + migrations/
backend/apps/common/datacategories.py        # shared DataCategory vocabulary
backend/apps/common/audit_context.py          # actor/ip/request_id capture helper
backend/tests/test_audit.py test_observability.py test_governance.py test_algorithms.py test_retention.py test_dbrole.py test_clean_setup.py (marker)
scripts/create_app_role.ps1  scripts/verify_clean_setup.ps1
docs/adr/ADR-014..018-*.md
frontend/src/app/admin/{observability,audit,retention,registry}/page.tsx + lib/adminApi.ts
```
Additive edits at implementation: `INSTALLED_APPS` (+4 apps), Celery beat schedule, root `urls.py` (+admin API routes), settings block for Phase 2 config, frontend nav.

---

## 8. Django App / Module Design

- **`audit`**: `record_audit(**)` service is the single write path; models are insert-only. Emitters call it from `accounts` views (login/logout/user CRUD/role change), `retention` (runs), `governance` (activation). Cross-app dependency flows one way: feature apps → `audit` service (via `common` interface to avoid tight coupling).
- **`observability`**: `MetricCollector` base + concrete collectors (RequestMetricCollector fed by middleware counters, TaskMetricCollector via Celery signals, HealthMetricCollector reusing `health` checks). A Celery task flushes sampled aggregates to `SystemMetric`.
- **`governance`**: pure registry + validation (checksum verify, config canonicalization/hash). No execution.
- **`retention`**: `registry.register(handler)`; `RetentionHandler` interface: `category`, `count(policy, cutoff)`, `delete(policy, cutoff, batch_size, dry_run) -> RetentionResult`. Handlers for `SECURITY_AUDIT` and `SYSTEM_METRIC` (the only real data now).
- **`common`**: adds `datacategories.py` (vocabulary) and `audit_context.py` (extract actor/ip/request_id from request/scope). Keeps `common` dependency-free of feature apps.

---

## 9. Database / Domain Models

**audit.AuditEvent** (insert-only): `id (UUID)`, `event_type (choices)`, `action`, `outcome (success/failure/denied)`, `actor (FK User SET_NULL)`, `actor_email` (snapshot), `actor_role` (snapshot), `target_type`, `target_id (char)`, `request_id`, `source` (django/celery/system), `ip_address (GenericIPAddress, null)`, `metadata (JSONB, sanitized)`, `created_at`. No `updated_at` (immutable).

**observability.SystemMetric**: `id`, `name (choices/registered)`, `runtime` (django/celery/system), `component`, `value (float)`, `unit`, `labels (JSONB, low-cardinality, validated)`, `host`, `process`, `bucket_start`, `created_at`. Pre-aggregated rows (not per-event).

**governance**:
- `AIModel`: `id`, `family`, `task (detection/tracking/prediction/anomaly/other)`, `provider`, `description`, `is_active`, timestamps. Unique `(family, task, provider)`.
- `AIModelVersion`: `id`, `model (FK)`, `version`, `provenance (pretrained/finetuned/platform_trained/imported/traditional_ml)`, `license`, `source_url`, `config (JSONB)`, `input_spec (JSONB)`, `output_schema_version`, `class_map (JSONB)`, `benchmark_summary (JSONB)`, `is_active`, `imported_at`. Unique `(model, version)`.
- `ModelArtifact`: `id`, `model_version (FK)`, `kind (weights/config/labels)`, `path`, `checksum_sha256`, `size_bytes`, `created_at`. **Path only — no blob.**
- `ModelEvaluation`: `id`, `model_version (FK)`, `dataset_ref`, `metrics (JSONB)`, `provenance_note`, `created_at`.
- `AlgorithmDefinition`: `id`, `key (unique)`, `name`, `category (congestion/queue/speed/signal/incident/...)`, `description`.
- `AlgorithmVersion`: `id`, `definition (FK)`, `version`, `config (JSONB)`, `config_hash`, `description`, `is_active`, `created_at`. Unique `(definition, version)`; immutable after create.
- `StoredArtifact` (minimal): `id`, `category (DataCategory)`, `path`, `checksum_sha256 (null)`, `size_bytes (null)`, `created_at`. Reusable file registry; no media engine.

**retention**:
- `RetentionPolicy`: `id`, `category (DataCategory, unique)`, `retention_days (int)`, `enabled (bool)`, `deletion_strategy (hard/archive)`, `batch_size`, `dry_run_default (bool)`, `config (JSONB)`, `last_run_at`, timestamps.
- `RetentionRun`: `id`, `policy (FK)`, `started_at`, `finished_at`, `dry_run (bool)`, `scanned`, `deleted`, `outcome (success/failed/partial)`, `error (text)`, `request_id/source`. Immutable record; also emits an `AuditEvent`.

Ownership/constraints: UUID PKs + timestamps via `common` mixins; FKs to `User` use `SET_NULL` (actor may be deleted) with snapshot fields preserving identity; JSONB validated/sanitized on write.

---

## 10. Database Schema Strategy

**Decision: Phase 2 models stay in `public`** (honoring ADR-013; no reversal). Rationale after analyzing migration behavior, cross-schema FKs, test-DB creation, permissions, backup, and DX: these are governance/ops tables of modest volume; cross-schema FKs (e.g., audit.actor → accounts.user) and Django's `search_path` handling add friction with zero current benefit. Domain schemas (`config/operational/analytical/ai`) remain reserved for Phase 3+ traffic/analytics tables where separation pays off. **No new ADR reversing 013**; ADR-015 records "Phase 2 remains in public, with mapping table for future migration." A forward note documents which Phase 2 tables would migrate to `ai` (governance) / `operational` (retention runs) / `analytical` (system_metric) **if/when** schema separation is activated.

---

## 11. PostgreSQL Least-Privilege Strategy

As §4.1 — `aitraffic_app` (NOSUPERUSER, NOCREATEROLE, CONNECT + USAGE/CREATE on `public`, owns app tables, narrow `CREATEDB` for test DBs). One role for migrate+runtime (Option A). Bootstrap via `scripts/create_app_role.ps1` run once with superuser; `.env` switches `DATABASE_URL`. Verified by full-suite pass under the new role + `rolsuper = false` assertion. Recorded in **ADR-014**.

---

## 12. Audit Architecture

- **Single write path:** `record_audit(event_type, action, outcome, actor, target_type, target_id, metadata=None, request=None, source="django")`. Sanitizes metadata (strips keys matching password/token/secret/authorization/cookie; truncates; rejects non-JSON-safe).
- **Immutability:** enforced by (a) no update/delete API, (b) model `save()` blocking updates (`pk` exists → raise), (c) DB defense: revoke UPDATE/DELETE on `audit_event` from `aitraffic_app` (grant INSERT/SELECT only) — DB-level immutability documented in ADR-016.
- **Transactional vs best-effort:** **business-critical, security-relevant events (user create/modify, role change, retention execution, model activation) are transactional** — written in the same DB transaction as the action; if audit insert fails, the action rolls back. **High-frequency/low-risk events (login success, logout)** are **best-effort** (post-commit hook; failure logged, does not break login). **Login failure** is best-effort + rate-aware (no lockout logic here). This split is explicit per event type in a table in the plan/ADR-016.
- **Fields:** §9. **Never stores** passwords/JWTs/secrets/cookies.
- **Retention:** governed by `RetentionPolicy(category=SECURITY_AUDIT)` — default long (e.g., 365 days), configurable, never below a safe floor.
- **Access:** read-only API restricted to `system_admin` (and optionally a future `auditor` role — not added now). No write API.
- **Query/indexing:** indexes on `(created_at)`, `(event_type, created_at)`, `(actor_id, created_at)`, `(target_type, target_id)`. Cursor/paginated list with filters (type, actor, outcome, date range).
- **Failure behavior:** transactional path → rollback + surfaced error; best-effort path → structured error log + a metric increment (`audit_emit_failures`), never silent.

---

## 13. Observability Architecture

Local-first, four **separate** concerns (never one generic table): **structured logs** (existing structlog), **audit events** (`audit_event`), **operational metrics** (`system_metric`), **performance measurements** (future CV; interface only), **business analytics** (future). Phase 2 implements logs (extend correlation), audit, and a bounded metrics foundation. No external observability stack. A `/api/v1/observability/summary` endpoint composes current health + recent metric aggregates for the admin UI.

## 14. Metrics Architecture

- **Model:** `SystemMetric` storing **pre-aggregated, sampled** rows (per bucket), not per-request writes. Low-cardinality `labels` validated against an allowlist per metric name (prevents cardinality explosion).
- **Collection:** in-memory counters/timers (request count/latency/errors via middleware; task duration/failures via Celery signals; health/heartbeat via `health` checks). A Celery beat task (default every 60s) **flushes aggregates** (count, sum, min, max, p95-approx) into `SystemMetric`, then resets counters. **No per-second DB writes.**
- **Which in PostgreSQL vs ephemeral:** aggregated operational metrics → PostgreSQL (bounded, retained). Raw high-frequency samples → ephemeral (in-memory/Redis, TTL). Future hardware/FPS/GPU metrics → interface reserved, **not** implemented (avoid writing hardware metrics every second).
- **Retention:** `RetentionPolicy(category=SYSTEM_METRIC)` default short (e.g., 30 days); older aggregates rolled up or dropped.
- **Config:** sampling interval, enabled flag, per-metric label allowlist — env for interval, DB for enable/policy.

## 15. AI Model Governance Architecture

`AIModel` → `AIModelVersion` → `ModelArtifact`/`ModelEvaluation` (§9). Records family/version/task/provider/provenance/license/config/input-spec/output-schema/class-map/benchmark/activation. **Artifacts by reference** (path + sha256 + size); weights never in PostgreSQL. Activation is single-active-per-(model) with an audited toggle. No inference, no downloads.

## 16. Algorithm Governance Architecture

`AlgorithmDefinition` + `AlgorithmVersion` (§9) — separate from AI models (deterministic components are **not** forced into the model abstraction). `config_hash` (canonical JSON → sha256) gives reproducibility; versions immutable after create. Later phases attach algorithm-version IDs to their outputs for traceability.

## 17. Model / Artifact Provenance

Provenance is explicit on `AIModelVersion.provenance` (pretrained/finetuned/platform_trained/imported/traditional_ml) and on `ModelArtifact` (path+checksum). Foundation enables the future question "what model+version+config+calibration+pipeline produced this result?" by giving stable version IDs + config hashes that later result tables will FK to. Phase 2 builds only the registry + IDs — **no result linkage yet** (no results exist).

## 18. Retention Policy Architecture

`RetentionPolicy` per `DataCategory` (§9/§13). No hardcoded durations anywhere — all reads go through the policy. Safe floors per category (audit can't be set below N days). `enabled`, `deletion_strategy`, `batch_size`, `dry_run_default`, `config` all DB-administered.

## 19. Retention Execution Architecture

- **Registry:** apps register a `RetentionHandler` per category. Phase 2 ships handlers for `SECURITY_AUDIT` and `SYSTEM_METRIC` only (the sole existing data). Unknown categories with no handler are skipped with a logged notice — **never a blind delete**.
- **Execution:** Celery beat task `evaluate_retention` iterates enabled policies → for each, calls handler with `cutoff = now - retention_days`, `batch_size`, `dry_run`. **Idempotent** (delete-by-cutoff is naturally repeatable). **Bounded** (batch loop with `max_batches`/`max_deletes` safety cap; a policy can never delete more than its configured ceiling in one run). **Dry-run** returns counts without deleting. Every run writes a `RetentionRun` + an `AuditEvent`. Failures → `outcome=failed/partial`, error captured, next run resumes (idempotent).
- **Safety against mass deletion:** hard cap per run; refuse to run if a policy's cutoff would match > `config.max_fraction` of the table without explicit override; audit-category deletions require the policy be explicitly enabled and above the floor; a global `RETENTION_DISABLED` kill-switch env var.
- **Manual trigger:** admin-only API to run a single policy in **dry-run by default**; real execution requires `system_admin` + explicit `dry_run=false`.

## 20. Storage Governance Foundation

Minimal `StoredArtifact` registry (path, category, checksum, size, created_at) — reusable now for `ModelArtifact`-style references, extensible for Phase 4 media. **No** upload/streaming/storage engine (that is Phase 4). Justified because governance/retention need a uniform artifact reference concept immediately; kept minimal.

## 21. Data Classification Vocabulary

`common/datacategories.py` — `DataCategory` TextChoices, extensible: `SECURITY_AUDIT`, `SYSTEM_METRIC`, `RAW_VIDEO`, `EVIDENCE_MEDIA`, `DETECTION_METADATA`, `TRACK_METADATA`, `TRAFFIC_MEASUREMENT`, `AGGREGATED_ANALYTICS`, `MODEL_ARTIFACT`, `SIMULATION_ARTIFACT`, `EXPORT`. **Vocabulary only** — no tables created for future categories. Retention/handlers exist only for categories with real data (audit, metrics; model_artifact optional).

---

## 22. Celery Task Architecture (respects ADR-002)

- `observability.tasks.flush_system_metrics` — beat every 60s; aggregates in-memory counters → `SystemMetric`.
- `retention.tasks.evaluate_retention` — beat daily (configurable); runs enabled policies (dry-run honored per policy).
- `retention.tasks.execute_policy(policy_id, dry_run)` — on-demand from admin API.
- `observability.tasks.rollup_metrics` (optional) — daily coarse rollup before drop.
- Keeps existing `write_worker_heartbeat`. **No CV/GPU work.** Worker remains `--pool=solo` + separate beat on Windows.

---

## 23. API Contracts (Phase 2, under `/api/v1/`, standard envelope, all authorized)

| Method | Path | Role |
|---|---|---|
| GET | `/audit/events` (filter: type, actor, outcome, from, to; paginated) | system_admin |
| GET | `/audit/events/{id}` | system_admin |
| GET | `/observability/summary` | system_admin, traffic_admin |
| GET | `/observability/metrics` (filter: name, runtime, from, to) | system_admin, traffic_admin |
| GET | `/retention/policies` | system_admin |
| GET/PATCH | `/retention/policies/{id}` (enable, days, batch, strategy) | system_admin |
| GET | `/retention/runs` (history) | system_admin |
| POST | `/retention/policies/{id}/run` (dry_run default true) | system_admin |
| GET/POST | `/governance/models` , `/governance/models/{id}/versions` | system_admin |
| POST | `/governance/versions/{id}/activate` | system_admin |
| GET/POST | `/governance/algorithms` , `/algorithms/{id}/versions` | system_admin |
| GET | `/governance/artifacts` | system_admin |

No write endpoints for audit. Retention real-execution gated (dry-run default). Registry writes system_admin only.

## 24. Permission Matrix (additions)

| Capability | system_admin | traffic_admin | operator/analyst/incident/viewer |
|---|:--:|:--:|:--:|
| View audit events | ✅ | ❌ | ❌ |
| View observability summary/metrics | ✅ | ✅ | ❌ |
| View/modify retention policies | ✅ | ❌ | ❌ |
| Run retention (dry-run) | ✅ | ❌ | ❌ |
| Run retention (real delete) | ✅ | ❌ | ❌ |
| Register/activate models & algorithms | ✅ | ❌ | ❌ |
| View model/algorithm registry | ✅ | ✅ (read) | ❌ |

Enforced server-side (new DRF permission classes reusing Phase 1 role infra). Frontend gating cosmetic.

## 25. Frontend Scope

Minimal admin-only pages under `/admin` (system_admin): **Observability** (health + metric summaries), **Audit log** (filterable table), **Retention** (policy list/edit + run history + dry-run button), **Registry** (models/algorithms read + activate). Reuses Phase 1 auth/api/context. **No** maps, cameras, traffic charts, or Ops Center. Role-aware nav adds an "Admin" section for system_admin.

## 26. Environment / Configuration Changes

New env (deployment-specific): `METRIC_SAMPLE_INTERVAL_SECONDS`, `RETENTION_ENABLED` (kill-switch), `RETENTION_EVAL_CRON`, `RETENTION_MAX_DELETES_PER_RUN`, `ARTIFACT_ROOT` (validated base path). DB-administered (not env): per-category retention days/enabled/strategy, metric enable flags. New `DATABASE_URL` uses `aitraffic_app` (changed by developer, not planning). No over-envify of business config.

## 27. ADRs Required

- **ADR-014** — Least-privilege DB role (single `aitraffic_app`, Option A, CREATEDB rationale).
- **ADR-015** — Phase 2 schema placement (remain in `public`; future mapping).
- **ADR-016** — Audit immutability + transactional-vs-best-effort emission split.
- **ADR-017** — Metrics model (aggregated/sampled, label allowlist, PG-vs-ephemeral).
- **ADR-018** — Time-series & partitioning strategy (see §28).

## 28. Time-Series & Partitioning Strategy (ADR-018)

Analyze future high-volume tables: `TrafficMeasurement` (highest), detection/track metadata, `SystemMetric`, future processing metrics. Direction: **plain PostgreSQL declarative RANGE partitioning by time**, partition key `created_at`/`bucket_start`, interval weekly or daily depending on volume, **introduced only when a table is projected to exceed ~10–50M rows** (i.e., Phase 6/8 for measurements — not now). Retention integrates by **dropping whole partitions** (cheap) instead of row deletes. `SystemMetric` (Phase 2) stays **unpartitioned** — bounded by sampling + short retention; partition later only if volume warrants. **TimescaleDB not needed** (native partitioning + our aggregation covers laptop scale; revisit only on measured need per D2). No future traffic tables created now.

## 29. Testing Strategy

- **Audit:** creation, immutability (update/delete blocked at model + DB), permission (only system_admin reads), sensitive-data exclusion (password/token/cookie stripped), actor-deletion → SET_NULL + snapshot retained, request-id correlation, transactional rollback on forced audit failure, best-effort login path survives audit failure.
- **Retention:** policy selection, dry-run (no deletion, correct counts), batch deletion, idempotency (re-run deletes nothing new), failure recovery (partial → resumes), handler registration (unknown category skipped safely), safety cap (never exceeds max), `RetentionRun` + `AuditEvent` produced, kill-switch honored.
- **Governance:** model/version create, `(model,version)` uniqueness, artifact checksum validation, provenance required, activate/deactivate single-active + audited, permissions.
- **Algorithms:** definition/version register, `config_hash` reproducibility, version immutability, `(definition,version)` uniqueness.
- **Metrics:** collector counts, sampler flush → `SystemMetric`, label allowlist rejection, retention drops old, PG-vs-ephemeral separation.
- **Infrastructure:** app runs as `aitraffic_app` (non-superuser assertion), new Celery tasks (eager), Redis interaction, **WebSocket regression + teardown-fix assertion**, and the **entire Phase 1 suite stays green** (no Phase 1 test removed).
- **Clean-setup:** `test_clean_setup`-style check driving `verify_clean_setup.ps1` (throwaway venv/db/temp frontend), non-destructive.

## 30. Failure-Testing Strategy

Audit insert failure (transactional → rollback; best-effort → logged, action proceeds). Retention: handler exception → run `partial/failed`, next run resumes; forced over-cap → refused; kill-switch on → no deletes. Metric flush failure → logged, counters preserved. DB role lacking a privilege → clear error, not silent. WS teardown → assert no lingering-connection error. Redis down → metric flush/heartbeat degrade visibly (reuse Phase 1 readyz failure pattern).

## 31. Security Requirements

All Phase 1 properties preserved. Additionally: audits exclude JWTs/passwords/secrets (sanitizer + test); artifact paths validated against `ARTIFACT_ROOT` (no traversal); retention real-execution + policy edits + registry writes are system_admin only; manual retention protected + dry-run default; audit read restricted; every destructive retention op produces a `RetentionRun` + `AuditEvent`; mass-deletion guards (§19). DB immutability grants for audit table.

## 32. Implementation Order (dependency-aware)

1. Verify Phase 1 baseline green (run suite as-is).
2. ADRs 014–018 authored.
3. **DB debt:** `create_app_role.ps1`; switch `.env`; re-run suite as `aitraffic_app`; assert non-superuser. (Developer performs the one-time bootstrap.)
4. **WS teardown fix** + regression assertion.
5. `common` additions: `DataCategory`, `audit_context`.
6. **`audit`** app: model + service + emitters + immutability + API + tests.
7. **`governance`** app: models + checksum + API + tests.
8. **`retention`** app: policy/run models + handler registry + audit/metric handlers + dry-run/bounded execution + tests.
9. **`observability`** app: `SystemMetric` + collectors + flush task + API + tests.
10. Celery beat schedules (metrics flush, retention eval).
11. APIs + permission classes wired; root URL additions.
12. Minimal admin UI pages.
13. Full Phase 2 tests + **Phase 1 regression**.
14. Failure tests.
15. Clean-setup reproducibility check.
16. Verification report.

## 33. Acceptance Criteria

- **AC2-1** Phase 1 regression suite green (66 tests) + all new tests pass.
- **AC2-2** App runs/migrates/tests as non-superuser `aitraffic_app`; superuser assertion fails for it.
- **AC2-3** WS teardown warning resolved (root cause fixed) or formally demonstrated + sanctioned mitigation.
- **AC2-4** `AuditEvent` durable + immutable (model + DB level).
- **AC2-5** Sensitive values excluded from audits (tested).
- **AC2-6** Audit access permission-controlled (system_admin only).
- **AC2-7** Model + algorithm version provenance reproducible (config hash, uniqueness, provenance).
- **AC2-8** Retention policies configurable (DB, no hardcoded durations).
- **AC2-9** Retention execution idempotent.
- **AC2-10** Dry-run retention works (no deletion).
- **AC2-11** Retention deletion bounded/safe (cap + kill-switch tested).
- **AC2-12** Retention runs produce `RetentionRun` + `AuditEvent`.
- **AC2-13** Existing data categories (audit, metrics) have working handlers.
- **AC2-14** System metrics collection bounded + configurable (sampled, allowlisted).
- **AC2-15** Phase 2 APIs permission-controlled.
- **AC2-16** Admin UI pages function where included.
- **AC2-17** Celery periodic tasks work.
- **AC2-18** No Phase 3+ functionality introduced.
- **AC2-19** Clean-setup reproducibility check passes non-destructively.

## 34. Verification Procedure

Run full suite (Phase 1 + Phase 2) under `aitraffic_app`; capture pass/fail/coverage. Manually: create users/roles → confirm audit rows (immutable, sanitized); edit a retention policy → dry-run (counts, no delete) → real run (bounded delete + `RetentionRun` + audit); register a model/version + artifact (checksum) + activate (audited); confirm metrics flushing into `SystemMetric` and old ones pruned; hit each API as authorized and unauthorized roles; load admin UI pages; verify WS still connects + no teardown error; run `verify_clean_setup.ps1` (throwaway env, auto-teardown). Produce report in Phase 0 §13 format.

## 35. Expected Deliverables

Four new apps (audit/observability/governance/retention) + `common` additions; `aitraffic_app` role + bootstrap script; WS teardown fix; retention policy+run+handlers (audit, metrics); `SystemMetric` + collectors + sampler; model/algorithm registries + artifact refs; admin APIs + permission classes; minimal admin UI; Celery schedules; ADRs 014–018; `verify_clean_setup.ps1`; full tests + green Phase 1 regression; `PHASE_2_VERIFICATION_REPORT.md`.

## 36. Known Risks

| ID | Risk | Mitigation |
|---|---|---|
| P2-R1 | Least-privilege role breaks migrations/tests | Grant table ownership + narrow CREATEDB; verify full suite before switching default |
| P2-R2 | WS teardown fix insufficient (Channels-internal conn) | Root-cause fix first; documented `--reuse-db` fallback if proven unfixable from tests |
| P2-R3 | Metric cardinality explosion | Label allowlist per metric; aggregated/sampled writes; short retention |
| P2-R4 | Retention mass-deletion accident | Hard caps, kill-switch, dry-run default, floors, audit of every run |
| P2-R5 | Audit write coupling slows auth | Transactional only for high-value events; login/logout best-effort post-commit |
| P2-R6 | Scope creep into traffic domain | Non-goals enforced; handlers/collectors only for existing data |
| P2-R7 | Schema-in-public revisited later causes churn | ADR-015 forward-mapping documents future moves; keep FKs simple now |
| P2-R8 | JSONB metadata leaking secrets | Central sanitizer + exclusion tests |

## 37. Estimated Implementation Effort

Solo + AI assist, this laptop, ~4–8 hrs/day. Estimates, not guarantees.

| Area | Optimistic | Realistic | High-complexity |
|---|---|---|---|
| Debt (DB role, WS fix, clean-setup) | 1.5 d | 3 d | 5 d |
| Audit app + emitters + tests | 2 d | 4 d | 6 d |
| Governance (models+algorithms) + tests | 2 d | 4 d | 6 d |
| Retention policy+execution+handlers + tests | 2.5 d | 4.5 d | 7 d |
| Observability/metrics + tasks + tests | 2 d | 3.5 d | 6 d |
| APIs + permissions | 1 d | 2 d | 3 d |
| Admin UI (4 pages) | 1.5 d | 3 d | 5 d |
| Regression + failure + verification report | 1.5 d | 3 d | 4 d |
| **Total** | **~14 d** | **~27 d** | **~42 d** |

Roughly **3 / 5–6 / 8–9 weeks** at a sustainable solo pace.

---

## Decisions Requiring Your Approval (before Phase 2 implementation)

1. **DB role model — Option A (single `aitraffic_app`) vs Option B (separate migration/runtime roles).** *Recommendation: A* (simplest secure for laptop-first; ADR-014). Consequence of A: one credential handles migrate+runtime; still non-superuser.
2. **Switch `DATABASE_URL` to `aitraffic_app` during Phase 2?** *Recommendation: yes* — resolve the debt now; you run the one-time bootstrap script, I do not change credentials during planning.
3. **Grant narrow `CREATEDB` to `aitraffic_app`** (so pytest/migrate work unchanged) vs pre-creating `test_aitraffic`. *Recommendation: grant CREATEDB* (low risk, best DX).

Defaults are applied if you simply approve; tell me to change any.

---

PHASE 2 PLAN STATUS: READY FOR REVIEW

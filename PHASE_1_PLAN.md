# PHASE 1 — PLATFORM FOUNDATION — IMPLEMENTATION PLAN

**Project:** AI Traffic Intelligence & Management Platform
**Phase:** 1 — Platform Foundation
**Depends on:** Phase 0 (APPROVED & FROZEN, 2026-07-15)
**Status:** READY FOR REVIEW — *no code will be written until explicitly approved.*
**Frozen decisions applied:** D1 single Postgres + 4 logical schemas · D2 plain Postgres partitioning · D3 native-free Redis else WSL2 · Next.js 15.3.4 + pnpm · native Windows first · 3-runtime split.

---

## 1. Exact Objectives & Scope

Build the **runnable skeleton** every later phase plugs into: a Django modular-monolith backend, a Next.js 15.3.4 frontend, working PostgreSQL + Redis, Celery + Channels wired and health-checkable, JWT auth with server-side role/permission enforcement, structured logging, and a minimal authenticated UI shell.

**In scope (Phase 1 only):**
1. Repository skeleton (backend + frontend + docs) — native Windows execution.
2. Django project with settings split (base/dev/test) and `.env` config.
3. PostgreSQL connection using the single-instance / four-schema model (schemas created; only `config`/auth tables populated this phase).
4. Redis running locally (native-free primary, WSL2 fallback) — used as Celery broker + Channels layer + cache.
5. Celery worker + beat wired with one trivial health task (`ping`).
6. Django Channels (ASGI) with one authenticated WebSocket endpoint (system heartbeat/echo foundation).
7. Custom email-based User model + Role/Permission system + JWT (access/refresh, rotation, blacklist).
8. Auth + user-management REST API (login, refresh, logout, me, admin user CRUD, roles list).
9. Health/readiness endpoints (`/api/healthz`, `/api/readyz`) that check DB + Redis.
10. Structured logging foundation (JSON, request-id correlation) across Django + Celery.
11. Standardized error-handling envelope (DRF exception handler).
12. Frontend: auth flow (login/logout), token handling, protected route shell, role-aware nav placeholder, health widget.
13. Base test suite (unit/integration/API/permission/failure categories) + CI-less local test runner config.
14. Foundational abstract models (`UUIDModel`, `TimeStampedModel`) reused by all future domains.

---

## 2. Explicit Non-Goals (Phase 1)

- ❌ No traffic-network models (City/Road/Lane/Camera) — **Phase 3**.
- ❌ No video upload / VideoSource — **Phase 4**.
- ❌ No CV runtime, detection, tracking, GPU code — **Phases 5–7**.
- ❌ No ProcessingSession engine — **Phase 5**.
- ❌ No observability metrics store / AI-governance tables / retention jobs — **Phase 2**.
- ❌ No dashboards, analytics, charts, maps beyond the auth shell — **Phase 12**.
- ❌ No SUMO, signals, prediction, twin.
- ❌ No Docker (optional, later). No cloud, no paid services.
- ❌ No real-time traffic data over the WebSocket — only a heartbeat/echo to prove the transport.
- ❌ No password-reset email flow / SMTP (admin-set passwords only this phase; email flow deferred).

---

## 3. Architecture Components Being Implemented

| Component | Phase 1 implementation | Deferred part |
|---|---|---|
| Django API (control plane) | Project, settings, DRF, auth, users, health | Domain APIs |
| PostgreSQL | Single instance, 4 schemas created, auth tables | Analytical/AI tables |
| Redis | Broker + channel layer + cache | Session command bus, live pub/sub |
| Celery | Worker + beat + `ping` task | Aggregation/reports/cleanup |
| Channels (ASGI) | Authenticated `system` WS consumer (heartbeat) | Live session channels |
| Auth/Authz | JWT + roles + permission enforcement | Object-level perms per domain |
| Logging | Structured JSON + request-id | Session/metric logs |
| Frontend | Next 15.3.4 shell, auth, protected routes | Ops dashboard |

The 3-runtime split is **established but only 2 runtimes carry real work** this phase (Django, Celery). The CV runtime is not built yet; its process boundary (Redis command bus + Postgres state) is reserved, not implemented.

---

## 4. Final Repository Structure (Phase 1)

```
ai-camera/                              # repo root (E:\ai camera)
├─ PHASE_0_ARCHITECTURE.md              # frozen (do not edit without ADR)
├─ PHASE_1_PLAN.md                      # this file
├─ README.md                            # native Windows setup (Phase 1)
├─ .gitignore
├─ .editorconfig
├─ docs/
│  └─ adr/                              # ADR-001..012 stubs authored as reached
├─ backend/
│  ├─ .env.example                      # committed; .env is git-ignored
│  ├─ pyproject.toml  (or requirements/*.txt)   # pinned deps
│  ├─ pytest.ini
│  ├─ manage.py
│  ├─ config/                           # Django project package
│  │  ├─ __init__.py
│  │  ├─ settings/
│  │  │  ├─ base.py
│  │  │  ├─ dev.py
│  │  │  └─ test.py
│  │  ├─ urls.py
│  │  ├─ asgi.py                        # Channels ASGI entry
│  │  ├─ wsgi.py
│  │  ├─ celery.py                      # Celery app
│  │  ├─ logging.py                     # structlog config
│  │  ├─ exceptions.py                  # DRF custom exception handler
│  │  └─ routing.py                     # Channels URLRouter
│  ├─ apps/
│  │  ├─ common/                        # abstract models, mixins, pagination, base perms
│  │  │  ├─ models.py                   # UUIDModel, TimeStampedModel
│  │  │  ├─ permissions.py              # role-based DRF permission classes
│  │  │  ├─ responses.py                # standard envelope helpers
│  │  │  └─ middleware.py               # request-id middleware
│  │  ├─ accounts/                      # User, Role, auth
│  │  │  ├─ models.py                   # User, Role, (Permission via Django)
│  │  │  ├─ managers.py                 # UserManager (email login)
│  │  │  ├─ serializers.py
│  │  │  ├─ views.py                    # auth + user CRUD
│  │  │  ├─ urls.py
│  │  │  └─ permissions.py
│  │  ├─ health/                        # healthz/readyz
│  │  │  ├─ views.py
│  │  │  └─ urls.py
│  │  └─ realtime/                      # Channels consumers
│  │     ├─ consumers.py                # SystemConsumer (heartbeat/echo)
│  │     └─ auth.py                     # WS JWT auth middleware
│  └─ tests/                            # pytest suite (mirrors apps/)
├─ frontend/
│  ├─ package.json                      # next 15.3.4, react 19, pinned
│  ├─ pnpm-lock.yaml                    # committed
│  ├─ tsconfig.json
│  ├─ next.config.ts
│  ├─ tailwind.config.ts
│  ├─ postcss.config.mjs
│  ├─ .env.local.example
│  ├─ eslint.config.mjs
│  └─ src/
│     ├─ app/                           # App Router
│     │  ├─ layout.tsx
│     │  ├─ page.tsx                    # redirects to /login or /dashboard
│     │  ├─ (auth)/login/page.tsx
│     │  └─ (app)/dashboard/page.tsx    # protected placeholder shell
│     ├─ lib/
│     │  ├─ api.ts                      # fetch wrapper + token refresh
│     │  ├─ auth.ts                     # auth state (context/zustand)
│     │  └─ config.ts                   # env access
│     ├─ components/                    # AppShell, Nav, HealthWidget, ProtectedRoute
│     └─ types/                         # shared TS types
└─ scripts/
   ├─ dev_backend.ps1                   # run migrate + runserver/uvicorn
   ├─ dev_worker.ps1                    # run celery worker + beat
   ├─ dev_frontend.ps1                  # pnpm dev
   └─ init_db.ps1                       # create db + schemas (idempotent)
```

*(Structure is the plan; nothing is created until approval.)*

---

## 5. Backend Application / Module Structure

Modular monolith via Django apps, each a bounded module:
- **`config/`** — project wiring only (settings, ASGI/WSGI, Celery, routing, logging, exception handler).
- **`apps/common`** — shared primitives every future app imports: `UUIDModel` (UUID PK), `TimeStampedModel` (created_at/updated_at), request-id middleware, standard response envelope, base DRF permission classes, pagination defaults.
- **`apps/accounts`** — custom `User` (email as username), `Role`, JWT auth views, user management. Owns the `auth` logical schema tables.
- **`apps/health`** — liveness/readiness.
- **`apps/realtime`** — Channels consumers + WS JWT auth. Heartbeat only this phase.

Import rule (enforced by review): `common` depends on nothing app-specific; feature apps depend on `common`; no app imports another feature app directly (future cross-module contracts go through services/interfaces).

---

## 6. Frontend Structure (Next.js 15.3.4)

- **App Router**, TypeScript strict, **pnpm** (lockfile committed).
- Route groups: `(auth)` public, `(app)` protected by a client-side guard **plus** every data call is authorized server-side (frontend guard is UX only).
- **State:** lightweight auth store (Zustand *or* React Context — ADR-frontend); server state via `@tanstack/react-query`.
- **API layer:** typed `fetch` wrapper in `lib/api.ts` handling base URL, `Authorization` header, 401 → silent refresh → retry, and standardized error envelope parsing.
- **Styling:** Tailwind CSS (v3.4.x pinned for stability; Tailwind v4 evaluated in a later ADR).
- **Env:** only `NEXT_PUBLIC_*` values exposed to the browser (API base URL, WS URL). No secrets in frontend.
- Phase 1 pages: `/login`, `/dashboard` (placeholder shell with role-aware nav + health widget + "who am I" panel). No feature UI.

---

## 7. PostgreSQL Setup & Configuration

- **Version:** PostgreSQL 16.x (native Windows installer).
- **Instance topology (D1):** one instance, one database `traffic_platform`, **four logical schemas**: `config`, `operational`, `analytical`, `ai`. Plus default auth/Django tables. Phase 1 populates `auth`-related tables (Django places them in `public` unless routed; accounts models pinned to `config` schema via `db_table`/`Meta` schema-qualified names or search_path — decided in ADR).
- **Partitioning (D2):** none needed in Phase 1 (no time-series yet); native declarative partitioning is introduced in Phase 2/8 for `TrafficMeasurement`. Documented now, not implemented.
- **Driver:** `psycopg` v3 (`psycopg[binary]`).
- **Setup script** `init_db.ps1`: create role, database, and the four schemas idempotently; set `search_path`. Documented in README.
- **Connections:** single pooled connection config in Django; `CONN_MAX_AGE` tuned for dev.
- **Migrations:** created only during implementation (after approval), never in planning.

---

## 8. Redis Setup Strategy (Windows, D3)

- **Requirement:** free, local, reliable, Redis-protocol compatible; no paid dependency.
- **Primary path (native):** evaluate **Memurai Developer Edition** (free for development, native Windows service, Redis 7.x-compatible, actively maintained). Verify it starts reliably and passes a `PING`/`SET`/`GET` + pub/sub smoke test.
- **Fallback path:** **Redis under WSL2** (official Redis, fully free/open-source) if the native option is unavailable or unreliable in this environment.
- **Decision recording:** whichever passes the Phase 1 verification smoke test becomes ADR-011's outcome. Both paths expose `redis://localhost:6379` so app config is identical.
- **Uses this phase:** Celery broker + result backend, Channels channel layer (`channels_redis`), Django cache. Health check pings Redis.
- **Note:** Redis is a *development* dependency; production/edge Redis will run on Linux later — no lock-in.

---

## 9. Celery & Django Channels Architecture

**Celery**
- App defined in `config/celery.py`, autodiscovers tasks.
- Broker + result backend = Redis.
- Worker + **beat** both run (beat scheduled but with no real periodic jobs yet beyond an optional heartbeat log).
- One task this phase: `common.tasks.ping` returning a timestamped ack, used by `/api/readyz` and tests to prove the worker path.
- Windows note: run worker with `--pool=solo` (or `threads`) for dev reliability (prefork is limited on Windows) — documented in `dev_worker.ps1`.

**Channels**
- ASGI entry `config/asgi.py`; `ProtocolTypeRouter` → HTTP (Django) + WebSocket (`realtime.routing`).
- Channel layer = `channels_redis`.
- `SystemConsumer` at `ws/system/`: authenticates via JWT (query param or subprotocol → `realtime/auth.py` middleware), then echoes a server heartbeat every N seconds and echoes client pings. **No traffic data.** Proves auth + transport + Redis channel layer.
- Dev ASGI served by **uvicorn** (or daphne) — documented.

---

## 10. Authentication & Authorization Architecture

- **Library:** `djangorestframework-simplejwt` with token blacklist app enabled.
- **Tokens:** short-lived **access** (e.g., 15 min) + longer **refresh** (e.g., 7 days) with **rotation** and **blacklist-on-logout/rotate**.
- **Login:** email + password → token pair.
- **Refresh:** rotate refresh, issue new access; old refresh blacklisted.
- **Logout:** blacklist the presented refresh token.
- **Authorization:** every REST endpoint declares required role(s)/permission(s) via DRF permission classes in `common/permissions.py`; enforced **server-side**. Frontend nav gating is cosmetic only.
- **WS auth:** JWT validated at connect; unauthenticated connections rejected.
- **Password storage:** Django's PBKDF2 (default) hasher; configurable.
- **User creation:** admin-only this phase (no self-registration).

---

## 11. User Roles & Permission Matrix

Roles frozen from Phase 0 (implemented as `Role` rows mapped to Django permission groups). A user has exactly one primary role (multi-role deferred).

| Role | Description |
|---|---|
| System Administrator | Full control incl. user & role management |
| Traffic Administrator | Manage traffic config (future domains); manage operators |
| Traffic Operator | Operate sessions/monitoring (future) |
| Traffic Analyst | Read analytics (future) |
| Incident Operator | Manage alerts/incidents (future) |
| Viewer | Read-only |

**Phase 1 permission matrix (only endpoints that exist this phase):**

| Capability / Endpoint | SysAdmin | TrafficAdmin | Operator | Analyst | IncidentOp | Viewer |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Login / Refresh / Logout | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /auth/me` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /roles` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /users` (list) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `POST /users` (create) | ✅ | ✅¹ | ❌ | ❌ | ❌ | ❌ |
| `PATCH /users/{id}` | ✅ | ✅¹ | self² | self² | self² | self² |
| `DELETE /users/{id}` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `POST /users/{id}/role` (assign role) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `GET/POST ws/system/` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Health endpoints | public (readyz may be restricted) | | | | | |

¹ Traffic Administrator may create/edit only non-admin roles (cannot mint System Administrators).
² "self" = users may edit their own profile fields (name, password), not their role or active status.
*(This matrix is enforced by permission-tests, §21.)*

---

## 12. Initial Database Models (Phase 1 only)

In `apps/common`:
- **`UUIDModel`** (abstract) — `id: UUID` primary key.
- **`TimeStampedModel`** (abstract) — `created_at`, `updated_at`.

In `apps/accounts` (schema `config`/auth):
- **`User`** — extends `AbstractBaseUser` + `PermissionsMixin`; fields: `id (UUID)`, `email (unique, USERNAME_FIELD)`, `full_name`, `is_active`, `is_staff`, `role (FK→Role, PROTECT)`, `date_joined`, timestamps. Custom `UserManager`.
- **`Role`** — `id`, `code (unique; enum of the 6 roles)`, `name`, `description`. Seeded via data migration/fixture at implementation time.
- Permissions leverage Django's built-in `Permission`/`Group` (Role ↔ Group mapping). No custom permission table this phase.
- **SimpleJWT blacklist tables** (`OutstandingToken`, `BlacklistedToken`) via its app.

**No other models.** Uniqueness: `User.email` unique; `Role.code` unique. Indexes: default PK + `User.email`. No time-series, no partitioning yet.

---

## 13. API Endpoint Contracts

Base path: `/api/v1`. All responses use the standard envelope (§19). Auth via `Authorization: Bearer <access>`.

| Method | Path | Auth | Body → Response |
|---|---|---|---|
| POST | `/auth/login` | public | `{email, password}` → `{access, refresh, user}` |
| POST | `/auth/refresh` | refresh token | `{refresh}` → `{access, refresh}` |
| POST | `/auth/logout` | authed | `{refresh}` → `204` (blacklisted) |
| GET | `/auth/me` | authed | → `{id, email, full_name, role, permissions[]}` |
| GET | `/roles` | authed | → `[{code, name, description}]` |
| GET | `/users` | admin | query: page, search → paginated `[user]` |
| POST | `/users` | admin | `{email, full_name, role, password}` → `201 {user}` |
| GET | `/users/{id}` | admin or self | → `{user}` |
| PATCH | `/users/{id}` | admin or self(limited) | partial → `{user}` |
| DELETE | `/users/{id}` | sysadmin | → `204` |
| POST | `/users/{id}/role` | sysadmin | `{role}` → `{user}` |
| GET | `/healthz` | public | → `{status:"ok"}` (liveness) |
| GET | `/readyz` | public/restricted | → `{db, redis, celery}` statuses (readiness) |

Errors return the standard error envelope with appropriate HTTP status. Pagination: DRF page-number, `page`/`page_size` (capped). Versioned under `/v1` to allow evolution.

**WebSocket:** `ws/system/` — connect with JWT; server sends `{type:"heartbeat", ts}` periodically; client may send `{type:"ping"}` → server `{type:"pong", ts}`.

---

## 14. WebSocket Foundation

- Transport proven end-to-end: authenticated connect → Redis channel layer → server heartbeat → clean disconnect.
- JWT auth middleware rejects unauthenticated/invalid tokens at connect (close code 4401).
- Heartbeat interval configurable via env.
- Reconnect handled client-side (frontend) with backoff; lossy by design.
- **No business data** flows yet — this only de-risks the real-time stack for later phases.

---

## 15. Environment Variable Specification

Backend `.env` (example committed as `.env.example`; real `.env` git-ignored):

| Var | Example | Purpose |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | settings selector |
| `DJANGO_SECRET_KEY` | (generated) | crypto secret |
| `DJANGO_DEBUG` | `true` | debug flag (dev only) |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | host allowlist |
| `DATABASE_URL` | `postgresql+psycopg://user:pw@localhost:5432/traffic_platform` | DB conn |
| `DB_SEARCH_PATH` | `config,public` | schema search path |
| `REDIS_URL` | `redis://localhost:6379/0` | broker/cache/channels |
| `CELERY_BROKER_URL` | `${REDIS_URL}` | Celery broker |
| `CELERY_RESULT_BACKEND` | `${REDIS_URL}` | results |
| `JWT_ACCESS_MINUTES` | `15` | access TTL |
| `JWT_REFRESH_DAYS` | `7` | refresh TTL |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | frontend origin |
| `WS_HEARTBEAT_SECONDS` | `20` | heartbeat interval |
| `LOG_LEVEL` | `INFO` | logging |
| `LOG_JSON` | `true` | structured logs on |

Frontend `.env.local`:

| Var | Example | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | REST base |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000/ws` | WS base |

No secrets in `NEXT_PUBLIC_*`. Config read through `lib/config.ts`.

---

## 16. Dependency List (exact versions — VERIFY before install)

> Versions are **planned targets to verify for mutual compatibility** at install time (Python 3.12, Windows). Pin exact resolved versions in the lockfile once verified. None are installed during planning.

**Backend (pin in `pyproject.toml`/requirements):**
- `Django==5.2.*` (LTS)
- `djangorestframework==3.16.*`
- `djangorestframework-simplejwt==5.3.*`
- `channels==4.*`
- `channels-redis==4.*`
- `celery==5.4.*`
- `redis==5.*` (python client)
- `psycopg[binary]==3.2.*`
- `django-environ==0.11.*` (env parsing)
- `django-cors-headers==4.*`
- `uvicorn[standard]==0.30.*` (dev ASGI) and/or `daphne==4.*`
- `structlog==24.*`
- `whitenoise==6.*` (static, optional)
- **Dev/test:** `pytest==8.*`, `pytest-django==4.*`, `pytest-asyncio==0.24.*`, `pytest-cov`, `factory-boy`, `freezegun`, `ruff` (lint/format)

**Frontend (pin in `package.json` + `pnpm-lock.yaml`):**
- `next@15.3.4`
- `react@19.*`, `react-dom@19.*`
- `typescript@5.*`
- `tailwindcss@3.4.*`, `postcss`, `autoprefixer`
- `@tanstack/react-query@5.*`
- `zustand@5.*` (or Context — ADR)
- `zod@3.*`
- `eslint` + `eslint-config-next@15.3.4`, `prettier`

**Package manager:** pnpm (Node.js LTS 20/22). Exact versions confirmed against Next 15.3.4 peer requirements before install.

---

## 17. Native Windows Development Setup (primary path)

Documented in `README.md`; no Docker required.

1. Install **Python 3.12**, **PostgreSQL 16**, **Node.js LTS + pnpm**, and Redis (Memurai native, else WSL2).
2. `python -m venv .venv` in `backend/`; activate; `pip install` pinned deps.
3. Copy `.env.example` → `.env`; fill secrets; run `scripts/init_db.ps1` (db + 4 schemas).
4. `scripts/dev_backend.ps1` → migrate + run ASGI (uvicorn) on :8000.
5. `scripts/dev_worker.ps1` → Celery worker (`--pool=solo`) + beat.
6. `frontend/`: `pnpm install`; copy `.env.local.example`; `scripts/dev_frontend.ps1` → Next dev on :3000.
7. Verify: open `/healthz`, `/readyz`, log in via UI, see heartbeat widget.

Windows-specific notes captured: Celery pool flag, Redis service start, `psycopg[binary]` wheels, PowerShell script execution policy.

---

## 18. Structured Logging Foundation

- **`structlog`** producing JSON logs (toggle to console renderer in dev via `LOG_JSON`).
- **Request-id middleware** (`common/middleware.py`) assigns/propagates an `X-Request-ID`; bound into every log line for correlation.
- Celery task logs include `task_id`; WS logs include `connection_id`.
- Standard fields: `ts, level, logger, event, request_id, user_id?, path?, status?, duration_ms?`.
- Log levels via `LOG_LEVEL`. No external log platform (local-first, per Phase 0 §34).
- This is the *foundation*; per-session/metric logging arrives in Phase 2.

---

## 19. Error-Handling Standards

- **Never hide exceptions; never fake data** (Phase 0 rule).
- **Standard success envelope:** `{ "data": <payload>, "meta": {...}? }`.
- **Standard error envelope:** `{ "error": { "code": "<machine_code>", "message": "<human>", "details": {...}? , "request_id": "..." } }`.
- **Custom DRF exception handler** (`config/exceptions.py`) maps DRF/validation/permission/not-found/throttle/unhandled errors to the envelope with correct HTTP status; unhandled 500s are logged with stack + request_id, but the response never leaks internals in non-debug.
- Validation errors return field-level `details`.
- Health endpoints report component failures explicitly (`readyz` returns 503 if DB/Redis down) rather than pretending healthy.

---

## 20. Security Requirements (Phase 1)

- Server-side authz on every endpoint + WS; frontend gating is cosmetic.
- JWT: short access TTL, refresh rotation + blacklist, logout revocation.
- Passwords hashed (PBKDF2); Django password validators enabled.
- CORS restricted to the frontend origin; CSRF not applicable to token API but session admin protected.
- Secrets only in `.env`/environment; `.env`, `.venv`, `node_modules`, build artifacts git-ignored.
- `DEBUG=false`-safe error responses (no stack leakage) verified even though dev uses debug.
- Rate limiting on auth endpoints (DRF throttle) to slow brute force.
- Audit-worthy auth events logged (login success/failure, logout) — lightweight; full `AuditEvent` model is Phase 2.
- No secrets in `NEXT_PUBLIC_*`.

---

## 21. Testing Strategy & Phase 1 Test Categories

Framework: pytest + pytest-django + pytest-asyncio. Target meaningful coverage of foundation logic (not a % gate this phase, but auth/permissions must be thoroughly covered).

| Category | Phase 1 tests |
|---|---|
| **Unit** | UserManager (email login), Role seeding, token config, envelope helpers, request-id middleware, logging binding |
| **Integration** | DB connectivity (4 schemas), Redis connectivity, Celery `ping` round-trip, migrations apply cleanly |
| **API** | login/refresh/logout/me, user CRUD, roles list, pagination, error envelope shape, health/readyz outputs |
| **Permission** | Full matrix (§11): each role × each endpoint → allowed/denied; admin-only guards; self-edit limits; TrafficAdmin cannot mint admins |
| **Failure** | invalid/expired/blacklisted token → 401; DB down → readyz 503; Redis down → readyz 503; malformed body → 400 envelope; WS bad token → reject 4401 |
| **WebSocket** | authed connect + heartbeat + ping/pong + clean disconnect (pytest-asyncio + Channels communicator) |

Deterministic: factories (`factory-boy`), `freezegun` for token expiry. No CV fixtures needed this phase.

---

## 22. Step-by-Step Implementation Order (with dependencies)

1. **Repo skeleton + docs + .gitignore** (blocks all). *(after approval)*
2. **Backend project scaffolding** — `config/` settings split, ASGI/WSGI. Dep: 1.
3. **`common` app** — abstract models, middleware, envelope, exception handler, logging. Dep: 2.
4. **PostgreSQL + `init_db.ps1`** — db, 4 schemas, Django DB config; first migration (common). Dep: 2.
5. **`accounts` app** — User/Role models, manager, migrations, Role seed. Dep: 3,4.
6. **JWT auth + auth endpoints** (login/refresh/logout/me). Dep: 5.
7. **User management endpoints + permission classes + matrix**. Dep: 6.
8. **Redis bring-up (D3 verify) + Celery** (`ping` task) + `readyz`. Dep: 4.
9. **Channels ASGI + `SystemConsumer` + WS JWT auth**. Dep: 6,8.
10. **`health` app** — healthz/readyz aggregating DB/Redis/Celery. Dep: 8.
11. **Backend test suite** (all categories). Dep: 3–10.
12. **Frontend scaffold** (Next 15.3.4 + Tailwind + pnpm). Dep: 1.
13. **API/auth layer** (`lib/api.ts`, token refresh, auth store). Dep: 6,12.
14. **Login page + protected shell + health widget + role-aware nav**. Dep: 13.
15. **Dev scripts + README native setup** + end-to-end smoke. Dep: all.
16. **Phase 1 verification report** (§24). Dep: all.

Critical path: 1→2→3/4→5→6→7/8/9/10→11 (backend) and 12→13→14 (frontend), converging at 15→16.

---

## 23. Phase 1 Acceptance Criteria

Each will be marked PASS / FAIL / NOT TESTED in the verification report.

- **AC-1** Repo skeleton matches §4; `.env` ignored; `.env.example` present.
- **AC-2** Backend boots (ASGI) on native Windows; `/api/healthz` → 200.
- **AC-3** PostgreSQL reachable; four schemas (`config, operational, analytical, ai`) exist; migrations apply cleanly.
- **AC-4** Redis running (native or WSL2) and reachable; choice recorded in ADR-011.
- **AC-5** Celery worker + beat run; `ping` task succeeds; reflected in `/readyz`.
- **AC-6** Channels WS `ws/system/` authenticates via JWT, streams heartbeat, rejects bad tokens.
- **AC-7** JWT login/refresh/logout work; rotation + blacklist verified.
- **AC-8** Full permission matrix (§11) enforced server-side (tests green).
- **AC-9** Standard success + error envelopes returned consistently.
- **AC-10** Structured JSON logs with request-id correlation across HTTP + Celery.
- **AC-11** `/readyz` returns 503 when DB or Redis is down (failure test).
- **AC-12** Frontend (Next 15.3.4) logs in, stores/refreshes tokens, shows protected shell + health widget; unauthenticated users redirected.
- **AC-13** All Phase 1 test categories present and passing; permission + failure tests included.
- **AC-14** README enables a clean native-Windows setup from zero.
- **AC-15** No later-phase features present (no camera/video/CV/domain models).

Phase 1 is **not** COMPLETE if any acceptance criterion FAILs.

---

## 24. Phase 1 Verification Procedure

1. Fresh-clone-style setup on the laptop following README only (no hidden steps).
2. Run `init_db.ps1`; confirm schemas via `\dn`.
3. Start backend, worker, frontend via scripts.
4. Hit `/healthz` (200) and `/readyz` (all green).
5. Run full pytest suite; capture pass/fail counts + coverage of accounts/permissions.
6. Manual: log in each role via UI; confirm nav gating + `/auth/me` correctness; confirm denied endpoints return 403.
7. WS: connect with valid + invalid token; observe heartbeat / rejection.
8. Failure drills: stop Postgres → `/readyz` 503; stop Redis → `/readyz` 503; expired token → 401.
9. Produce the Phase-1 completion report in the Phase-0 §13 format (What built / files / DB / API / tests / perf / limitations / acceptance / status).

---

## 25. Expected Deliverables

- Backend skeleton (config + common + accounts + health + realtime) running natively.
- PostgreSQL with four schemas + accounts migrations + Role seed.
- Redis operational (documented choice) + Celery worker/beat + `ping`.
- Channels heartbeat WS with JWT auth.
- JWT auth + user management API + enforced role matrix.
- Structured logging + standardized error handling.
- Next.js 15.3.4 frontend: login, token handling, protected shell, health widget, role-aware nav.
- Test suite across all Phase 1 categories (green).
- `README.md` native-Windows setup + dev scripts.
- ADR-001 (frontend), ADR-002 (runtime split — foundation portion), ADR-011 (Redis choice) authored.
- Phase 1 verification report.

---

## 26. Known Technical Risks (Phase 1)

| ID | Risk | Mitigation |
|---|---|---|
| P1-R1 | Celery on native Windows unreliable (prefork) | Use `--pool=solo`/threads for dev; document; production uses Linux |
| P1-R2 | Redis native option (Memurai) licensing/reliability | Verify via smoke test; WSL2 Redis fallback; both expose same URL |
| P1-R3 | Next 15.3.4 / React 19 peer-dependency churn | Pin exact versions + committed lockfile; verify peers before install (§16) |
| P1-R4 | Schema-qualified models add ORM friction | Decide schema placement in ADR; keep accounts in `config`, default others in `public` until domains arrive |
| P1-R5 | WS JWT auth edge cases (expiry mid-connection) | Auth at connect; reconnect on 401; token refresh client-side; tested |
| P1-R6 | psycopg3 / Django 5.2 Windows wheel issues | Use `psycopg[binary]`; verify import on Python 3.12 before proceeding |
| P1-R7 | ASGI server choice (uvicorn vs daphne) for Channels | Standardize on one in dev script; document; both supported |
| P1-R8 | Tailwind v3 vs v4 decision drift | Pin v3.4.x now; v4 migration is a later, isolated ADR |

---

**PHASE 1 PLAN STATUS: READY FOR REVIEW**

*No code, dependencies, migrations, or repository changes have been made. Awaiting explicit approval before implementing Phase 1.*

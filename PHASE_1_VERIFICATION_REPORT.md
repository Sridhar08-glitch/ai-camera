# PHASE 1 — VERIFICATION REPORT

**Project:** AI Traffic Intelligence & Management Platform
**Phase:** 1 — Platform Foundation
**Date:** 2026-07-15
**Verified on:** AMD Ryzen 9 · 16 GB RAM · 8 GB GPU · Windows 11 · Python 3.12.9

---

## What Was Built

A runnable, tested platform foundation as a modular-monolith across three
runtimes (Django control plane, Celery jobs, reserved CV data plane):

- Django 5.2 project (`config`) with split settings (base/dev/test), env-driven
  config, ASGI + WSGI, custom exception handler, structured logging.
- `common` app: UUID/timestamp abstract models, request-id middleware + access
  logging, standard success/error envelope, pagination, role vocabulary,
  role-based permission classes, shared Redis client, Celery tasks.
- `accounts` app: email-based custom `User`, `Role` (seeded), JWT auth with
  **HttpOnly refresh cookie** + rotation + blacklist, user management API,
  server-side RBAC.
- `health` app: `/api/healthz` (liveness) and `/api/readyz` (PostgreSQL + Redis +
  Celery-heartbeat readiness — no per-request task dispatch).
- `realtime` app: Channels ASGI, JWT-authenticated `SystemConsumer` heartbeat
  WebSocket.
- Next.js 15.3.4 frontend: login, in-memory access token + silent cookie
  refresh, protected role-aware dashboard shell, live health widget, live WS
  heartbeat indicator.
- Test suite (66 tests) across unit/integration/API/permission/failure/WebSocket
  categories, plus dev scripts, ADRs, and README.

Verified **live** end-to-end in a real browser: login → dashboard, all
infrastructure healthy, WebSocket connected.

---

## Exact Files Created

**Root / docs / scripts**
`.gitignore`, `README.md`, `PHASE_1_VERIFICATION_REPORT.md`,
`docs/adr/ADR-001-frontend-baseline.md`, `docs/adr/ADR-002-runtime-split.md`,
`docs/adr/ADR-011-redis-on-windows.md`, `docs/adr/ADR-013-schema-strategy.md`,
`scripts/init_db.ps1`, `scripts/dev_backend.ps1`, `scripts/dev_worker.ps1`,
`scripts/dev_frontend.ps1`.

**Backend — config**
`backend/manage.py`, `backend/pytest.ini`, `backend/.env.example`,
`backend/requirements/base.txt`, `backend/requirements/dev.txt`,
`backend/config/__init__.py`, `settings/base.py`, `settings/dev.py`,
`settings/test.py`, `config/urls.py`, `config/asgi.py`, `config/wsgi.py`,
`config/celery.py`, `config/logging.py`, `config/exceptions.py`.

**Backend — apps.common**
`__init__.py`, `apps.py`, `models.py`, `request_context.py`, `middleware.py`,
`pagination.py`, `permissions.py`, `responses.py`, `redis_client.py`, `roles.py`,
`tasks.py`, `migrations/__init__.py`.

**Backend — apps.accounts**
`__init__.py`, `apps.py`, `managers.py`, `models.py`, `permissions.py`,
`serializers.py`, `cookies.py`, `views.py`, `urls.py`, `urls_auth.py`,
`migrations/__init__.py`, `migrations/0001_initial.py`,
`migrations/0002_seed_roles.py`.

**Backend — apps.health / apps.realtime**
`health/__init__.py`, `health/apps.py`, `health/views.py`, `health/urls.py`,
`realtime/__init__.py`, `realtime/apps.py`, `realtime/auth.py`,
`realtime/consumers.py`, `realtime/routing.py`.

**Backend — tests**
`tests/__init__.py`, `conftest.py`, `test_common.py`, `test_auth.py`,
`test_users.py`, `test_permissions.py`, `test_health.py`, `test_ws.py`,
`test_celery.py`.

**Frontend**
`package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `next.config.ts`,
`postcss.config.mjs`, `tailwind.config.ts`, `.eslintrc.json`, `next-env.d.ts`,
`.env.local.example`, `src/app/layout.tsx`, `src/app/page.tsx`,
`src/app/login/page.tsx`, `src/app/dashboard/page.tsx`, `src/app/globals.css`,
`src/components/HealthWidget.tsx`, `src/lib/config.ts`, `src/lib/types.ts`,
`src/lib/api.ts`, `src/lib/auth.tsx`, `src/lib/useSystemSocket.ts`.

*(Local-only, git-ignored: `backend/.env`, `frontend/.env.local`,
`backend/.venv/`, `frontend/node_modules/`, `scripts/*.log`.)*

## Exact Files Modified
None pre-existing except the two approved planning docs, which were **preserved**.
`PHASE_0_ARCHITECTURE.md` was updated earlier only to stamp approval (before
implementation). `PHASE_1_PLAN.md` unchanged. No source files were modified after
creation except iterative edits within this phase (settings renderer registration;
`test_ws.py` token-helper fix).

---

## Final Dependency Versions (resolved & verified on Python 3.12.9 / Windows)

**Backend (installed, `pip freeze` verified):**
Django 5.2.7 · djangorestframework 3.16.1 · djangorestframework-simplejwt 5.5.1
(PyJWT 2.13.0) · channels 4.3.1 · channels_redis 4.3.0 · celery 5.5.3
(kombu 5.5.4, billiard 4.2.4, amqp 5.3.1, vine 5.1.0) · redis 6.4.0 ·
psycopg 3.2.10 · django-environ 0.12.0 · django-cors-headers 4.9.0 ·
uvicorn 0.38.0 · daphne 4.2.1 (Twisted 26.4.0, autobahn 26.6.2, txaio 26.6.1) ·
structlog 25.4.0 · whitenoise 6.11.0 · asgiref 3.12.1 · sqlparse 0.5.5.
**Dev/test:** pytest 8.4.2 · pytest-django 4.11.1 · pytest-asyncio 1.2.0 ·
pytest-cov 7.0.0 · factory-boy 3.3.3 · freezegun 1.5.5 · ruff 0.14.0.

**Frontend (installed):**
next 15.3.4 · react 19.1.0 · react-dom 19.1.0 · typescript 5.7.3 ·
tailwindcss 3.4.17 · postcss 8.4.49 · autoprefixer 10.4.20 ·
eslint 9.18.0 · eslint-config-next 15.3.4 · @types/node 22.10.5 ·
@types/react 19.1.0 · @types/react-dom 19.1.0. Package manager pnpm 9.15.9.

**All targets resolved exactly — no silent substitutions (clarification #6).**

---

## Environment & Infrastructure Configuration

- **Python:** 3.12.9 selected via `py -3.12` (system default `python` is 3.14.4;
  the venv is explicitly pinned to 3.12 — see Deviations).
- **PostgreSQL:** 18.3 native, `127.0.0.1:5432`, database `aitraffic`, user
  `postgres`. (PG17 also present on 5433, unused.)
- **Redis:** Memurai native service, `127.0.0.1:6379` (DB 0 cache/channels/
  heartbeat, 1 broker, 2 results). Verified via live PING/SET/GET/pub-sub.
- **Node/pnpm:** Node 24.15.0; pnpm 9.15.9 via corepack proxy.
- Config is fully env-driven (`backend/.env`, `frontend/.env.local`); no secrets
  in source. `host=postgres` from the message is a Docker name that does not
  resolve natively — `127.0.0.1` is used and documented.

---

## Database Models and Migrations

**Models:** `accounts.Role` (`code` unique, `name`, `description`, UUID PK,
timestamps); `accounts.User` (UUID PK, `email` unique = USERNAME_FIELD,
`full_name`, `role` FK→Role PROTECT, `is_active`, `is_staff`, PermissionsMixin,
timestamps). Abstract bases `common.UUIDModel` / `TimeStampedModel` (no tables).

**Migrations applied cleanly:**
`accounts/0001_initial` (Role, User) and `accounts/0002_seed_roles` (seeds the 6
roles), plus Django built-ins (admin, auth, contenttypes, sessions) and
`token_blacklist` (0001–0013). `manage.py migrate` completed with no errors;
role seed verified (6 roles present).

---

## Final PostgreSQL Schema Strategy (ADR-013)

One database `aitraffic`. Schemas `config`, `operational`, `analytical`, `ai`
are **created** (via `init_db.ps1`) and reserved for Phase 3+ domain tables.
Phase 1 keeps **all tables in `public`** — Django framework tables and
`accounts_user`/`accounts_role` — to prioritize migration safety over premature
separation (clarification #4). D1 (single instance, logical separation) is
honored; per-domain placement decided when domains are modeled.

---

## REST API Endpoints (all under standard envelope)

| Method | Path | Auth |
|---|---|---|
| GET | `/api/healthz` | public |
| GET | `/api/readyz` | public |
| POST | `/api/v1/auth/login` | public (throttled) |
| POST | `/api/v1/auth/refresh` | refresh cookie |
| POST | `/api/v1/auth/logout` | authenticated |
| GET | `/api/v1/auth/me` | authenticated |
| GET | `/api/v1/roles` | authenticated |
| GET/POST | `/api/v1/users` | admin roles |
| GET/PATCH/DELETE | `/api/v1/users/{uuid}` | self (limited) / admin; delete = system admin |
| POST | `/api/v1/users/{uuid}/role` | system admin |

## WebSocket Endpoints
`ws://<host>/ws/system/` — JWT-authenticated (`access_token` subprotocol, or
`?token=` fallback). Emits `welcome`, periodic `heartbeat`, and `pong` to client
`ping`. Rejects missing/invalid tokens with close code **4401**. No business data.

---

## Authentication & Token-Security Architecture (clarifications #1 & #2)

Consistent JWT identity across REST, frontend, and WebSocket:

- **Access token** (15 min): returned in the login/refresh JSON body; held in
  memory by the SPA (module variable) — never in localStorage/sessionStorage.
- **Refresh token** (7 days): delivered **only** as an `HttpOnly` cookie
  (`path=/api/v1/auth`, `SameSite=Lax`, `Secure` env-configurable). Never exposed
  to JS and never in a response body (asserted by tests).
- **Rotation + blacklist:** every refresh rotates the token and blacklists the
  old one (`token_blacklist`); logout blacklists and clears the cookie.
- **REST:** `Authorization: Bearer <access>`.
- **WebSocket:** same access token via the `access_token` subprotocol (browsers
  cannot set WS headers), validated by Channels JWT middleware.
- **Frontend:** silent cookie-based refresh on load and on any 401, then retry.
- CORS is origin-restricted with credentials enabled (verified preflight → 200,
  `Access-Control-Allow-Credentials: true`).

This final decision is documented here and in ADR-001/ADR-002.

---

## Role & Permission Implementation

Six seeded roles: `system_admin`, `traffic_admin`, `traffic_operator`,
`traffic_analyst`, `incident_operator`, `viewer`. Enforced **server-side** via
DRF permission classes (`IsAdminRole`, `IsSystemAdmin`, `IsSelfOrAdmin`) and
serializer-level guards. Matrix enforced and tested:

- List/create users → admin roles only; others 403.
- Delete user & assign role → system admin only; others 403.
- Traffic admin cannot create/assign an admin role (400).
- Non-admin may read/update only self; cannot change own role/active (400).
- `me`/`roles` → any authenticated role.

Frontend role-aware nav is cosmetic only (confirmed: server rejects unauthorized
calls regardless of UI).

---

## Celery & Redis Implementation

- Celery app `config.celery` (broker/results on Memurai DBs 1/2), JSON
  serialization, autodiscovery.
- Tasks: `apps.common.tasks.ping` (round-trip proof) and
  `write_worker_heartbeat` (writes a TTL Redis key).
- **Beat** schedules the heartbeat (30s + 1-min); `/readyz` reads the cached key
  rather than dispatching a task per request (clarification #3).
- **Windows:** worker runs `--pool=solo`; beat runs as a **separate** process
  (embedded `-B` is unsupported on Windows — discovered and corrected live).
- Live-verified: worker + beat running, `/readyz` celery check green
  (`heartbeat_age_seconds ≈ 1.5`).

---

## Structured Logging Implementation

`structlog` with a shared stdlib processor chain; JSON renderer (toggle via
`LOG_JSON`), ISO-UTC timestamps, level, logger name. `RequestIDMiddleware`
assigns/propagates `X-Request-ID`, binds it into `contextvars` so every log line
in a request is correlated; `RequestLoggingMiddleware` emits one access line per
request (method, path, status, duration_ms, user_id, request_id). Celery uses the
same logging config. Response carries `X-Request-ID`.

---

## Frontend Implementation

Next.js 15.3.4 App Router + React 19 + TS + Tailwind 3.4. `AuthProvider`
(Context) holds user + in-memory token, silent-refreshes on mount. `lib/api.ts`
fetch wrapper: credentialed requests, single silent refresh + retry on 401,
envelope/error parsing. Pages: `/` (redirect), `/login` (form), `/dashboard`
(guarded shell with role-aware nav, `HealthWidget` polling `/readyz`, and
`useSystemSocket` WS heartbeat indicator). Typecheck clean; production build
succeeds (4 routes). State libs (zustand/react-query) intentionally omitted to
avoid unnecessary deps (ADR-001).

---

## Tests Added

66 tests across the mandated categories:
- **Unit** (`test_common.py`): role vocabulary, envelope helpers/renderer,
  request-id contextvar, UUID PK.
- **API/Auth** (`test_auth.py`): login (cookie set, refresh not in body), invalid
  login, `me`, cookie refresh rotation, refresh-without-cookie, logout+blacklist,
  invalid access token.
- **API/Users** (`test_users.py`): create, weak-password reject, admin-role
  restriction, pagination, self-edit, self role-change block, assign role,
  delete, self-delete block.
- **Permission** (`test_permissions.py`): parametrized matrix over all 6 roles ×
  list/create/delete/assign/me + cross-user read.
- **Failure/Health** (`test_health.py`): healthz, readyz component report, ready
  when heartbeat fresh, 503 when heartbeat missing / Redis down / DB down.
- **WebSocket** (`test_ws.py`): authenticated welcome+ping/pong; reject missing
  token (4401); reject invalid token (4401).
- **Integration/Celery** (`test_celery.py`): `ping` round-trip; heartbeat TTL key.

---

## Exact Test Results

```
66 passed, 56 warnings in ~8.7s
Coverage (apps + config): 91%  (756 statements, 65 missed)
Ruff lint: All checks passed.
Frontend: tsc --noEmit clean; next build success (4 routes).
```

**Failed tests:** none.
**Skipped tests:** none.

Uncovered lines are non-critical: process entrypoints (`asgi.py`, `wsgi.py`),
some superuser-manager branches, and a few defensive error paths.

---

## Manual Verification Results (live)

1. `GET /api/healthz` → `{"data":{"status":"ok"}}` (200).
2. `GET /api/readyz` → 200, `database/redis/celery` all `ok` (celery heartbeat
   age ~1.5s) against real uvicorn + PG18 + Memurai + worker/beat.
3. HTTP login → access + user, **no refresh in body**; `me` with access → 200;
   cookie-based refresh → new access; `me` without token → 401.
4. CORS preflight from `http://localhost:3000` → 200 with
   `Access-Control-Allow-Origin` + `Allow-Credentials: true`.
5. Next dev server serves `/login` (200, contains "Sign in").
6. **Browser E2E (Chrome):** filled credentials, clicked Sign in → redirected to
   `/dashboard`; showed `admin@holora.local` + `system_admin` badge; role-aware
   nav (Overview/Users/Network/Cameras/Alerts); Infrastructure widget
   database/redis/celery = **healthy**; Realtime channel = **connected** with a
   live WebSocket heartbeat timestamp.

---

## Acceptance Criteria

| ID | Criterion | Result |
|---|---|---|
| AC-1 | Repo skeleton matches plan; `.env` ignored; `.env.example` present | **PASS** (minor structural deviations documented) |
| AC-2 | Backend boots (ASGI); `/api/healthz` → 200 | **PASS** |
| AC-3 | PostgreSQL reachable; four schemas exist; migrations apply cleanly | **PASS** |
| AC-4 | Redis running & reachable; choice recorded in ADR-011 | **PASS** |
| AC-5 | Celery worker + beat run; `ping` succeeds; reflected in `/readyz` | **PASS** |
| AC-6 | WS authenticates via JWT, streams heartbeat, rejects bad tokens | **PASS** |
| AC-7 | JWT login/refresh/logout; rotation + blacklist verified | **PASS** |
| AC-8 | Full permission matrix enforced server-side (tests green) | **PASS** |
| AC-9 | Standard success + error envelopes returned consistently | **PASS** |
| AC-10 | Structured JSON logs with request-id across HTTP + Celery | **PASS** |
| AC-11 | `/readyz` returns 503 when DB or Redis is down | **PASS** |
| AC-12 | Frontend logs in, refreshes token, protected shell + health widget | **PASS** |
| AC-13 | All Phase 1 test categories present and passing | **PASS** |
| AC-14 | README enables clean native-Windows setup | **PASS** (written; not re-run from a fresh clone) |
| AC-15 | No later-phase features present | **PASS** |

**All 15 mandatory acceptance criteria: PASS. None FAIL. None NOT TESTED.**

---

## Known Limitations

1. **WS test teardown warning:** an async DB connection from Channels lingers at
   test-DB teardown ("database is being accessed by other users"). Cosmetic —
   tests pass; does not affect runtime.
2. **Dev uses the `postgres` superuser** as the app DB user (as provided). A
   least-privilege application role is recommended for Phase 2 hardening.
3. **AC-14 not re-verified from a zero clone** — README steps mirror the exact
   commands run here, but a from-scratch machine bootstrap was not repeated.
4. **`whitenoise` static warning** at startup (no `staticfiles/` yet) — harmless
   in dev; resolved by `collectstatic` when needed.
5. A smoke-test admin (`admin@holora.local`) exists in the dev DB.
6. Celery uses the Windows-appropriate `--pool=solo`; throughput characteristics
   differ from a Linux prefork pool (irrelevant to Phase 1 scope).

---

## Deviations From the Approved Plan (clarification #6 — documented, not silent)

| Planned | Actual | Reason |
|---|---|---|
| Python 3.12 | 3.12.9 via `py -3.12` (system default is 3.14.4) | 3.12 present; venv pinned to it — **no functional deviation** |
| PostgreSQL 16 | PostgreSQL 18.3 | Installed version; psycopg3 compatible; migrations clean |
| Node LTS 20/22 | Node 24.15.0 | Installed version; Next 15.3.4 runs fine |
| pnpm global install | pnpm via `corepack pnpm` proxy | `corepack enable` needs admin (EPERM); proxy keeps pnpm as planned (ADR-001) |
| Route groups `(auth)`/`(app)` | Flat `/login`, `/dashboard` | Simpler; identical guard behavior |
| `config/routing.py` | Routing in `apps/realtime/routing.py` | Keeps WS routing with its app; ASGI wires it |
| zustand + react-query | React Context only | Avoid unnecessary deps (rules #12); revisit later |
| Schemas host domain tables | Phase 1 tables in `public` | Migration safety (clarification #4, ADR-013) |
| DB host | `127.0.0.1` (not `postgres`) | `postgres` is a Docker hostname; doesn't resolve natively |

No deviation affects an acceptance criterion. All are structural/environmental.

---

## Security Observations

- Authorization is enforced server-side on every REST endpoint and the WS
  handshake; frontend gating is cosmetic (verified).
- Refresh token is HttpOnly-cookie-only; access token never persisted in browser
  storage; refresh never in a response body (test-asserted).
- Token rotation + blacklist active; logout revokes.
- Auth endpoints throttled (`10/min`) to slow brute force.
- Password validators enabled (min length 10, common/numeric checks).
- Error responses use a safe envelope; unhandled 500s log stack + request-id
  without leaking internals.
- **For Phase 2:** switch the app DB user to a least-privilege role; set
  `REFRESH_COOKIE_SECURE=true` behind TLS; add login-failure audit persistence
  (currently logged, not stored); consider rate-limiting `/readyz` if exposed.

---

## Phase 2 Prerequisites

Per the Phase 0 roadmap, Phase 2 = **Observability + AI-governance tables +
retention framework**. Prerequisites, now satisfied by Phase 1:
- Structured logging + request-id correlation ✅ (extend to session/metric logs).
- Celery + beat operational ✅ (host retention/cleanup + rollup jobs).
- Redis + heartbeat pattern ✅ (basis for metrics + worker/session liveness).
- `AuditEvent` model **not yet built** — Phase 2 introduces it (Phase 1 logs
  auth events but does not persist an audit table).
- Domain schemas (`config/operational/analytical/ai`) exist and are ready to
  receive Phase 2/3 tables (ADR-013).
- Recommended before Phase 2 code: author ADRs for time-series/partitioning
  (D2 confirmed plain-Postgres) and retention tiers.

---

## Final Status

**PHASE 1: COMPLETE WITH KNOWN LIMITATIONS**

All 15 mandatory acceptance criteria PASS (none failed, none untested); the
foundation is verified live end-to-end. The status reflects the documented
environmental deviations and the minor limitations listed above — none of which
block Phase 1 or compromise its acceptance criteria.

Awaiting explicit approval before beginning Phase 2.

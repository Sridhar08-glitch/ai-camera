# ADR-014 — Least-privilege PostgreSQL application role

**Status:** Accepted (Phase 2) · Supersedes the Phase 1 use of the `postgres` superuser as the app identity.

## Decision
The application connects as a single dedicated non-superuser role **`aitraffic_app`**
(D1 = Option A). This one role handles both Django migrations and normal runtime
for the laptop-first local environment. No separate migration/runtime roles.

## Role attributes (verified)
- `LOGIN`, password supplied via environment (never hardcoded).
- **NOSUPERUSER**, **NOCREATEROLE**, **NOREPLICATION**, **NOBYPASSRLS**.
- **CREATEDB** — granted for local development only, so Django/pytest can create
  and drop isolated test databases (`test_aitraffic`). This is a **development
  convenience**, NOT a production runtime requirement; a future production runtime
  role must NOT receive `CREATEDB`.
- Privileges in `aitraffic`: `CONNECT`; `USAGE` + `CREATE` on schema `public`;
  ownership of application tables (so migrations can ALTER/DROP their own objects).

## Bootstrap
`scripts/create_app_role.ps1` is idempotent, run once by the developer using the
`postgres` superuser (only for administrative bootstrap). It reads the password
from `$env:AITRAFFIC_APP_PASSWORD` — no hardcoded secret. The `postgres`
superuser is **not** altered or deleted. After bootstrap, `.env`'s `DATABASE_URL`
uses `aitraffic_app`; the superuser is no longer the runtime identity.

## Consequences
- Removes cluster-wide superuser from normal runtime (the real risk).
- `aitraffic_app` owns its tables, which is relevant to audit immutability — see
  ADR-016 for the honest enforcement boundary this creates.

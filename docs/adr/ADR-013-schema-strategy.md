# ADR-013 — PostgreSQL schema strategy (clarification #4)

**Status:** Accepted (Phase 1)

## Decision
One PostgreSQL database (`aitraffic`), with **logical domain separation** realized
progressively. In Phase 1, **all tables live in the `public` schema** — including
Django framework tables and the `accounts` (auth) tables.

The four domain schemas `config`, `operational`, `analytical`, `ai` are **created**
by `scripts/init_db.ps1` so they exist for later phases, but Phase 1 does **not**
route any model into a custom schema.

## Rationale (clarification #4)
Forcing Django/auth tables into custom schemas adds ORM `search_path` and
migration complexity for no Phase 1 benefit. Migration safety and maintainability
take priority. Domain tables introduced in Phase 3+ (network, cameras, sessions,
measurements) will be placed into the appropriate domain schema at the time they
are modeled, when the separation actually pays off.

## Consequence
- D1 (single instance, logical separation) is honored: one DB, schemas reserved.
- No `search_path` gymnastics in Phase 1; `accounts_user` / `accounts_role` and
  framework tables are in `public`.
- Revisit per-domain schema placement in a Phase 3 ADR.

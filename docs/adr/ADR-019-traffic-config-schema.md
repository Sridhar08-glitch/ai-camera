# ADR-019 — Traffic Configuration Schema Strategy

**Status:** Accepted (Phase 3) · Does NOT modify ADR-013 or ADR-015.

## Decision (D1 = Option A)
Phase 3 traffic-network tables live in the **`public`** PostgreSQL schema (table
prefix `network_*`, app `network`). The reserved `config` schema stays empty.

## Rationale
- Django 5.2 has no first-class per-model schema support; using `config` requires
  a `db_table = 'config"."x'` quoting hack or a `search_path` override, both of
  which complicate migrations, introspection, test-DB creation, and third-party
  compatibility.
- PostGIS is not installed (ADR-020), so there is no spatial-schema benefit.
- No backup/permission/tablespace isolation is needed at laptop scale.
- Logical domain separation is already achieved by the `network` app + `network_*`
  table naming.

## Reconsideration triggers
Move `network_*` tables into `config` only when one becomes true: (a) a second
physical database / separate operational-analytical storage is introduced;
(b) schema-level backup or permission isolation is required; (c) PostGIS is
adopted and a spatial schema is warranted; (d) table count/ops make grouping
genuinely valuable.

## Future migration path
`ALTER TABLE network_x SET SCHEMA config;` per table — a **metadata-only**
operation — plus a Django `db_table`/`search_path` update and a data-migration to
keep it reversible. No data copy required.

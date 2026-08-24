# ADR-016 — Audit architecture & immutability guarantees

**Status:** Accepted (Phase 2)

## Decision
A durable, append-only `audit.AuditEvent` model with a single write path
(`audit.services.record_audit`). No update/delete anywhere in normal operation.

## Immutability — honest enforcement boundary
Under the approved **single-role** architecture (ADR-014), `aitraffic_app` **owns**
the `audit_event` table. Table ownership means ordinary `REVOKE UPDATE/DELETE`
does **not** provide absolute protection: an owner can re-`GRANT` to itself, `ALTER`,
or `DROP` objects. We therefore do **not** claim absolute DB-level immutability.

We implement three layers and state exactly what each guarantees:

1. **Application-enforced** — the audit REST API is strictly read-only (no update
   or delete routes exist). Guarantee: no HTTP workflow can mutate audit rows.
2. **ORM-enforced** — `AuditEvent.save()` rejects updates (existing PK → raise);
   `AuditEvent.delete()` raises; a custom manager/queryset makes `.update()` and
   `.delete()` raise. Guarantee: no Django ORM path (instance or bulk) can mutate
   or delete audit rows.
3. **Database-enforced (UPDATE)** — a `BEFORE UPDATE` trigger on `audit_event`
   raises an exception. Guarantee: **no UPDATE** from any client (ORM, raw SQL,
   psql, non-Django clients) can alter an existing audit row; the trigger **fires
   for the owner role too**. This makes recorded audit content tamper-proof against
   modification at the database level.
   - **DELETE is intentionally NOT blocked at the database.** Expired audit rows
     must be purgeable by the retention engine (§ retention). Deletion is instead
     controlled above the database: no delete API exists, the default ORM manager
     forbids `delete()`/bulk delete, and only the dedicated `retention_objects`
     manager — used solely by the bounded, audited retention engine — can delete,
     and only rows older than the configured retention floor.
   - Caveat (stated honestly): because `aitraffic_app` owns the table, it could
     `DROP`/`DISABLE` the UPDATE trigger via explicit DDL. The application never
     does this. Absolute immutability against a determined owner would require a
     separate table-owner role or a superuser-owned table with restricted grants —
     deliberately **not** introduced in Phase 2 to avoid role complexity on a
     laptop-first setup.

**Net guarantee:** audit records **cannot be modified** through any path
(application, ORM, or database — UPDATE is DB-enforced), and **cannot be deleted**
through any application or default-ORM path. Deletion occurs only via the
controlled, bounded, audited retention engine for rows past their retention period.
The only bypass is an out-of-band DDL action by the owning role, documented above.

## Emission policy — transactional vs best-effort
- **Transactional** (audit insert in the same DB transaction as the action; audit
  failure rolls back the action): user create/modify, activation/deactivation,
  role change, retention execution, model/algorithm activation.
- **Best-effort** (emitted after commit; failure is logged + counted, never breaks
  the action): login success, login failure, logout.

## Fields, sanitization, retention, access
- Fields: id, event_type, action, outcome, **actor_id (UUID, by value — NOT a
  foreign key)** + actor_email/actor_role snapshots, target_type, target_id,
  request_id, source, ip_address, metadata (JSONB), created_at. No `updated_at`.
- **Actor is referenced by value, not FK.** A foreign key with `SET_NULL` would
  make Django issue an `UPDATE audit_event SET actor_id=NULL` when a user is
  deleted — which the immutability trigger (correctly) blocks, and which would also
  mutate a supposedly-immutable record. Storing `actor_id` as a plain UUID plus
  snapshot fields means user deletion never touches audit rows; the actor's
  identity survives via the snapshot. This strengthens, rather than weakens,
  immutability.
- Sanitizer strips keys matching password/token/secret/authorization/cookie/jwt and
  drops non-JSON-safe values. Passwords, JWTs, refresh tokens, auth headers, cookies
  are never stored.
- Retention via `RetentionPolicy(category=SECURITY_AUDIT)` with a safe floor.
- Read access: `system_admin` only. No write API.

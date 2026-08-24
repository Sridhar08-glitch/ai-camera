# ADR-015 — Phase 2 schema placement

**Status:** Accepted (Phase 2) · Does NOT reverse ADR-013.

## Decision
All Phase 2 tables (audit, observability, governance, retention) live in the
`public` schema, consistent with ADR-013. The reserved domain schemas
(`config`, `operational`, `analytical`, `ai`) remain unused until Phase 3+ traffic
and analytics tables, where physical separation actually pays off.

## Rationale
Analyzed migration behavior, cross-schema foreign keys (e.g., audit.actor →
accounts.user), Django `search_path` handling, test-DB creation, role permissions,
backup/restore, and developer experience. For modest-volume governance/ops tables
the friction of custom schemas outweighs any benefit now.

## Forward mapping (non-binding, for when separation is activated)
- `ai`: AIModel, AIModelVersion, ModelArtifact, ModelEvaluation, AlgorithmDefinition,
  AlgorithmVersion.
- `operational`: RetentionPolicy, RetentionRun, StoredArtifact.
- `analytical`: SystemMetric.
- `public`: AuditEvent (security), or a dedicated `audit` schema later.

Moving these later is a separate ADR + data migration; not undertaken in Phase 2.

// Thin typed helpers over apiFetch for the Phase 2 admin pages.
import { apiFetch } from "./api";

export interface AuditEvent {
  id: string;
  event_type: string;
  action: string;
  outcome: string;
  actor_email: string;
  actor_role: string;
  target_type: string;
  request_id: string;
  created_at: string;
}

export interface RetentionPolicy {
  id: string;
  category: string;
  retention_days: number;
  enabled: boolean;
  dry_run_default: boolean;
  last_run_at: string | null;
}

export interface RetentionRun {
  id: string;
  dry_run: boolean;
  scanned: number;
  deleted: number;
  outcome: string;
}

export interface Paginated<T> {
  results?: T[];
}

export const listAuditEvents = () =>
  apiFetch<AuditEvent[]>("/audit/events");

export const listRetentionPolicies = () =>
  apiFetch<RetentionPolicy[]>("/retention/policies");

export const runRetention = (id: string, dryRun: boolean) =>
  apiFetch<RetentionRun>(`/retention/policies/${id}/run`, {
    method: "POST",
    body: JSON.stringify({ dry_run: dryRun }),
  });

export interface ObservabilitySummary {
  window_hours: number;
  metric_counts: number;
  totals: Record<string, number>;
}

export const getObservabilitySummary = () =>
  apiFetch<ObservabilitySummary>("/observability/summary");

export interface AIModelRow {
  id: string;
  family: string;
  task: string;
  provider: string;
  is_active: boolean;
}

export const listModels = () => apiFetch<AIModelRow[]>("/governance/models");

// Generic CRUD helpers for the Phase 3 network configuration resources.
import { apiFetch } from "./api";

export interface Row {
  id: string;
  [key: string]: unknown;
}

export function listResource(path: string, params: Record<string, string> = {}) {
  const qs = new URLSearchParams(params).toString();
  return apiFetch<Row[]>(`/network/${path}${qs ? `?${qs}` : ""}`);
}

export function createResource(path: string, body: Record<string, unknown>) {
  return apiFetch<Row>(`/network/${path}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function archiveResource(path: string, id: string) {
  return apiFetch<null>(`/network/${path}/${id}`, { method: "DELETE" });
}

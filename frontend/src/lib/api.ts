// Typed fetch wrapper.
//
// Token security (clarification #1/#2): the refresh token lives ONLY in an
// HttpOnly cookie set by the backend and is never touched by JS. The access
// token is short-lived and kept in memory here (module variable) — never in
// localStorage/sessionStorage. On a 401 we attempt a single silent refresh
// (cookie-based) and retry. All requests send credentials so the cookie flows.

import { config } from "./config";
import type { ApiError, User } from "./types";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export class ApiRequestError extends Error {
  status: number;
  error: ApiError;
  constructor(status: number, error: ApiError) {
    super(error.message);
    this.status = status;
    this.error = error;
  }
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init.headers ?? {}),
    },
  });
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err: ApiError = body?.error ?? {
      code: "error",
      message: `HTTP ${res.status}`,
    };
    throw new ApiRequestError(res.status, err);
  }
  return (body?.data ?? body) as T;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<T> {
  let res = await rawFetch(path, init);
  if (res.status === 401 && retry && path !== "/auth/refresh") {
    const refreshed = await tryRefresh();
    if (refreshed) {
      res = await rawFetch(path, init);
    }
  }
  return parse<T>(res);
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await rawFetch("/auth/refresh", { method: "POST" });
    if (!res.ok) return false;
    const body = await res.json();
    setAccessToken(body?.data?.access ?? null);
    return Boolean(accessToken);
  } catch {
    return false;
  }
}

// --- Auth API ------------------------------------------------------------

export async function login(
  email: string,
  password: string,
): Promise<{ access: string; user: User }> {
  const res = await rawFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const data = await parse<{ access: string; user: User }>(res);
  setAccessToken(data.access);
  return data;
}

export async function logout(): Promise<void> {
  try {
    await rawFetch("/auth/logout", { method: "POST" });
  } finally {
    setAccessToken(null);
  }
}

export async function restoreSession(): Promise<User | null> {
  const ok = await tryRefresh();
  if (!ok) return null;
  return apiFetch<User>("/auth/me");
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

# ADR-001 — Frontend baseline

**Status:** Accepted (Phase 1)

## Decision
Next.js 15.3.4 (App Router) + React 19.1.0 + TypeScript 5.7 + Tailwind CSS 3.4.
Package manager is pnpm 9.15.9.

## Context / notes
- Environment has Node.js 24.15.0 (newer than the planned LTS 20/22). Next 15.3.4
  runs on it; documented as a minor deviation.
- The corepack **global shim** could not be installed (`corepack enable` requires
  admin write to `C:\Program Files\nodejs`, EPERM). pnpm is therefore invoked via
  the corepack **proxy** (`corepack pnpm ...`) with `COREPACK_HOME` under
  `%LOCALAPPDATA%`. pnpm remains the package manager as planned.
- Tailwind v3.4 chosen over v4 for stability (v4 migration deferred to a later ADR).
- State management: React Context (no zustand/react-query in Phase 1) to avoid
  unnecessary dependencies; may be revisited when server-state complexity grows.

## Token security (frontend side)
- Access token kept in memory only (module variable), never in localStorage.
- Refresh token is an HttpOnly cookie managed entirely by the backend.
- Silent refresh on load + on 401 restores sessions without persisting tokens in JS.

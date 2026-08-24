"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { HealthWidget } from "@/components/HealthWidget";
import { useSystemSocket } from "@/lib/useSystemSocket";

// Role-aware navigation placeholder (features arrive in later phases).
const NAV_BY_ROLE: Record<string, string[]> = {
  system_admin: ["Overview", "Users", "Network", "Cameras", "Alerts"],
  traffic_admin: ["Overview", "Network", "Cameras", "Alerts"],
  traffic_operator: ["Overview", "Cameras", "Alerts"],
  traffic_analyst: ["Overview", "Analytics"],
  incident_operator: ["Overview", "Alerts"],
  viewer: ["Overview"],
};

export default function DashboardPage() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const { status, lastHeartbeat } = useSystemSocket(Boolean(user));

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-slate-400">Loading…</p>
      </main>
    );
  }

  const nav = NAV_BY_ROLE[user.role ?? "viewer"] ?? ["Overview"];

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 bg-panel p-4">
        <h1 className="mb-6 text-lg font-semibold">Traffic Ops</h1>
        <nav className="space-y-1">
          {nav.map((item) => (
            <div
              key={item}
              className="rounded px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              {item}
            </div>
          ))}
          {["system_admin", "traffic_admin", "traffic_operator"].includes(user.role ?? "") && (
            <Link
              href={user.role === "traffic_operator" ? "/admin/videos" : "/admin/observability"}
              className="mt-4 block rounded border border-slate-700 px-3 py-2 text-sm text-sky-300 hover:bg-slate-800"
            >
              Platform Admin →
            </Link>
          )}
        </nav>
      </aside>

      <main className="flex-1 p-6">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400">Signed in as</p>
            <p className="font-medium">
              {user.email}{" "}
              <span className="ml-2 rounded bg-slate-700 px-2 py-0.5 text-xs">
                {user.role}
              </span>
            </p>
          </div>
          <button
            onClick={logout}
            className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600"
          >
            Sign out
          </button>
        </header>

        <div className="grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
          <HealthWidget />
          <div className="rounded-lg bg-panel p-4">
            <h2 className="mb-3 text-sm font-semibold text-slate-300">
              Realtime channel
            </h2>
            <p className="text-sm">
              Status:{" "}
              <span
                className={
                  status === "connected"
                    ? "text-emerald-400"
                    : "text-amber-400"
                }
              >
                {status}
              </span>
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Last heartbeat: {lastHeartbeat ?? "—"}
            </p>
          </div>
        </div>

        <p className="mt-8 text-xs text-slate-600">
          Phase 1 foundation. Traffic features arrive in later phases.
        </p>
      </main>
    </div>
  );
}

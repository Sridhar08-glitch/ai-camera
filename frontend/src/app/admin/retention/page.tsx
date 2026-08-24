"use client";

import { useEffect, useState } from "react";
import {
  RetentionPolicy,
  RetentionRun,
  listRetentionPolicies,
  runRetention,
} from "@/lib/adminApi";

export default function RetentionPage() {
  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [lastRun, setLastRun] = useState<Record<string, RetentionRun>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRetentionPolicies()
      .then(setPolicies)
      .catch(() => setError("Failed to load policies"));
  }, []);

  async function dryRun(id: string) {
    try {
      const run = await runRetention(id, true);
      setLastRun((prev) => ({ ...prev, [id]: run }));
    } catch {
      setError("Dry-run failed");
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Retention Policies</h1>
      {error && <p className="mb-3 text-red-400">{error}</p>}
      <div className="space-y-3">
        {policies.map((p) => (
          <div key={p.id} className="rounded-lg bg-panel p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{p.category}</p>
                <p className="text-sm text-slate-400">
                  {p.retention_days} days · {p.enabled ? "enabled" : "disabled"}
                </p>
              </div>
              <button
                onClick={() => dryRun(p.id)}
                className="rounded bg-sky-600 px-3 py-1.5 text-sm hover:bg-sky-500"
              >
                Dry-run
              </button>
            </div>
            {lastRun[p.id] && (
              <p className="mt-2 text-xs text-slate-400">
                Last dry-run: scanned {lastRun[p.id].scanned}, would delete{" "}
                {lastRun[p.id].scanned - lastRun[p.id].deleted} · outcome{" "}
                {lastRun[p.id].outcome}
              </p>
            )}
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-600">
        Real deletion requires the API with dry_run=false (system_admin only).
      </p>
    </div>
  );
}

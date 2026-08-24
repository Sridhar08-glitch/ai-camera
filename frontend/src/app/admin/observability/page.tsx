"use client";

import { useEffect, useState } from "react";
import { ObservabilitySummary, getObservabilitySummary } from "@/lib/adminApi";

export default function ObservabilityPage() {
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getObservabilitySummary()
      .then(setSummary)
      .catch(() => setError("Failed to load observability summary"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Observability</h1>
      {error && <p className="text-red-400">{error}</p>}
      {loading && !error && <p className="text-slate-400">Loading metrics…</p>}
      {summary && (
        <div className="grid max-w-xl grid-cols-2 gap-4">
          <div className="rounded-lg bg-panel p-4">
            <p className="text-sm text-slate-400">Metric rows (1h)</p>
            <p className="text-2xl font-semibold">{summary.metric_counts}</p>
          </div>
          {Object.entries(summary.totals ?? {}).map(([name, value]) => (
            <div key={name} className="rounded-lg bg-panel p-4">
              <p className="text-sm text-slate-400">{name}</p>
              <p className="text-2xl font-semibold">{value}</p>
            </div>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs text-slate-600">
        Aggregated, sampled operational metrics (flushed by Celery beat).
      </p>
    </div>
  );
}

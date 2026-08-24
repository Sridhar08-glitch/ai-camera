"use client";

import { useEffect, useState } from "react";
import { AIModelRow, listModels } from "@/lib/adminApi";

export default function RegistryPage() {
  const [models, setModels] = useState<AIModelRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch(() => setError("Failed to load model registry"));
  }, []);

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">AI Model Registry</h1>
      {error && <p className="text-red-400">{error}</p>}
      {models.length === 0 && !error && (
        <p className="text-slate-500">No models registered yet.</p>
      )}
      <div className="space-y-2">
        {models.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between rounded-lg bg-panel p-4"
          >
            <div>
              <p className="font-medium">
                {m.family} <span className="text-slate-400">[{m.task}]</span>
              </p>
              <p className="text-sm text-slate-400">{m.provider || "—"}</p>
            </div>
            <span
              className={m.is_active ? "text-emerald-400" : "text-slate-500"}
            >
              {m.is_active ? "active" : "inactive"}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-600">
        Governance metadata only — no weights are stored in the database.
      </p>
    </div>
  );
}

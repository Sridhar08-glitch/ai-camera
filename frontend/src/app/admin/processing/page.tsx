"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ProcessingSession,
  RuntimeStatus,
  getRuntimeStatus,
  listSessions,
} from "@/lib/processingApi";

const STATE_COLOR: Record<string, string> = {
  completed: "text-emerald-400",
  running: "text-sky-400",
  queued: "text-slate-300",
  failed: "text-red-400",
  cancelled: "text-amber-400",
  stopped: "text-amber-400",
  paused: "text-sky-300",
};

export default function ProcessingListPage() {
  const [sessions, setSessions] = useState<ProcessingSession[]>([]);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listSessions().then(setSessions).catch(() => setError("Failed to load sessions"));
    getRuntimeStatus().then(setRuntime).catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 4000); // poll; DB is source of truth
    return () => clearInterval(t);
  }, [load]);

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Processing Sessions</h1>
      <p className="mb-4 text-sm text-slate-500">
        Phase 5 validates the processing infrastructure (decode → sample → frame interface).
        No AI detection is performed.
      </p>

      <div className="mb-4 rounded bg-panel px-4 py-2 text-sm">
        CV runtime:{" "}
        {runtime ? (
          <span className={runtime.cv_runtime_available ? "text-emerald-400" : "text-amber-400"}>
            {runtime.cv_runtime_available ? "available" : "offline"}
          </span>
        ) : (
          <span className="text-slate-500">…</span>
        )}
        {runtime && (
          <span className="ml-3 text-slate-500">
            device: {runtime.gpu.mode}
            {runtime.gpu.devices[0] ? ` (${runtime.gpu.devices[0].name})` : ""}
          </span>
        )}
      </div>

      {error && <p className="text-red-400">{error}</p>}

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-slate-400">
            <th className="py-2">Session</th>
            <th>Status</th>
            <th>Progress</th>
            <th>Processed</th>
            <th>Snapshot</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.id} className="border-b border-slate-800">
              <td className="py-2">
                <Link href={`/admin/processing/${s.id}`} className="text-sky-400 hover:underline">
                  {s.id.slice(0, 8)}…
                </Link>
              </td>
              <td className={STATE_COLOR[s.state] ?? "text-slate-300"}>{s.state}</td>
              <td>{s.progress_percent != null ? `${s.progress_percent.toFixed(0)}%` : "—"}</td>
              <td>{s.frames_processed}</td>
              <td className="font-mono text-xs text-slate-500">{s.snapshot_hash.slice(0, 10)}…</td>
              <td className="text-slate-500">{new Date(s.created_at).toLocaleString()}</td>
            </tr>
          ))}
          {sessions.length === 0 && (
            <tr>
              <td colSpan={6} className="py-6 text-center text-slate-500">
                No processing sessions yet. Start one from a validated video.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

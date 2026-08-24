"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ProcessingSession,
  cancelSession,
  getSession,
  isTerminal,
  pauseSession,
  resumeSession,
  retrySession,
  stopSession,
} from "@/lib/processingApi";
import DetectionsPanel from "./DetectionsPanel";

export default function ProcessingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [s, setS] = useState<ProcessingSession | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getSession(id).then(setS).catch(() => setError("Failed to load session"));
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 2000); // poll live progress; DB is authoritative
    return () => clearInterval(t);
  }, [load]);

  const act = (fn: (id: string) => Promise<ProcessingSession>) => () =>
    fn(id).then(setS).catch((e) => setError(e?.error?.message ?? "action failed"));

  if (error) return <p className="text-red-400">{error}</p>;
  if (!s) return <p className="text-slate-400">Loading…</p>;

  const terminal = isTerminal(s.state);
  const isDetector = (s.processing_params as { processor?: string })?.processor === "detector";
  const rows: [string, string][] = [
    ["State", s.state + (s.error_code ? ` (${s.error_code})` : "")],
    ["Video", s.video_id.slice(0, 8) + "…"],
    ["Snapshot", s.snapshot_hash.slice(0, 16) + "…"],
    ["Progress", s.progress_percent != null ? `${s.progress_percent.toFixed(1)}%` : "unknown total"],
    ["Frames decoded", s.frames_decoded.toString()],
    ["Frames processed", s.frames_processed.toString()],
    ["Current source ts", s.current_pts_seconds != null ? `${s.current_pts_seconds.toFixed(3)} s` : "—"],
    ["Processing FPS", s.processing_fps != null ? s.processing_fps.toFixed(1) : "—"],
    ["Device", s.device || "—"],
    ["Runtime", s.runtime_id || "—"],
    ["Retry of", s.retry_of ? s.retry_of.slice(0, 8) + "…" : "—"],
  ];

  return (
    <div>
      <button onClick={() => router.push("/admin/processing")} className="mb-4 text-sm text-slate-400 hover:text-slate-200">
        ← Processing Sessions
      </button>
      <h1 className="mb-1 text-xl font-semibold">Session {s.id.slice(0, 8)}…</h1>
      <p className="mb-4 text-sm text-slate-500">
        Infrastructure validation only — no vehicle detection, tracking, or counting.
      </p>

      {s.progress_percent != null && (
        <div className="mb-4 h-2 w-full max-w-md overflow-hidden rounded bg-slate-800">
          <div className="h-full bg-sky-500" style={{ width: `${s.progress_percent}%` }} />
        </div>
      )}

      <table className="text-sm">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-b border-slate-800">
              <td className="py-2 pr-6 text-slate-400">{k}</td>
              <td className="py-2 font-mono">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-6 flex flex-wrap gap-3">
        {s.state === "running" && (
          <button onClick={act(pauseSession)} className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600">Pause</button>
        )}
        {s.state === "paused" && (
          <button onClick={act(resumeSession)} className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600">Resume</button>
        )}
        {!terminal && (
          <>
            <button onClick={act(stopSession)} className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600">Stop</button>
            <button onClick={act(cancelSession)} className="rounded bg-red-900 px-4 py-2 text-sm hover:bg-red-800">Cancel</button>
          </>
        )}
        {terminal && (
          <button
            onClick={() => retrySession(id).then((n) => router.push(`/admin/processing/${n.id}`)).catch((e) => setError(e?.error?.message ?? "retry failed"))}
            className="rounded bg-sky-800 px-4 py-2 text-sm hover:bg-sky-700">
            Retry
          </button>
        )}
      </div>

      {isDetector && <DetectionsPanel sessionId={id} />}
    </div>
  );
}

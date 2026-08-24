"use client";

// Phase 6 detections viewer. Renders per-frame boxes (canonical normalized XYXY),
// class + confidence + producing provider. Raw video frames are deliberately NOT
// fetched or shown (privacy, §32) — boxes are drawn on a neutral canvas.
//
// When detections come from the deterministic TEST provider, a prominent
// "TEST PROVIDER — NOT REAL AI DETECTION" banner is shown. No counts, tracking,
// or speed are displayed.

import { useCallback, useEffect, useState } from "react";
import {
  Detection,
  FrameDetectionBatch,
  listDetections,
} from "@/lib/processingApi";

const CLASS_COLORS: Record<string, string> = {
  CAR: "#38bdf8",
  BUS: "#a78bfa",
  TRUCK: "#f59e0b",
  MOTORCYCLE: "#34d399",
  BICYCLE: "#f472b6",
  PEDESTRIAN: "#f87171",
};

function BoxOverlay({ detections }: { detections: Detection[] }) {
  // 16:9 neutral canvas; boxes positioned by normalized coords (percent).
  return (
    <div className="relative aspect-video w-full max-w-xl overflow-hidden rounded border border-slate-700 bg-slate-900">
      <div className="absolute inset-0 grid place-items-center text-xs text-slate-600">
        normalized coordinate space (no raw frame shown)
      </div>
      {detections.map((d, i) => {
        const [x1, y1, x2, y2] = d.bbox;
        const color = CLASS_COLORS[d.canonical_class] ?? "#94a3b8";
        return (
          <div
            key={i}
            className="absolute border-2"
            style={{
              left: `${x1 * 100}%`,
              top: `${y1 * 100}%`,
              width: `${(x2 - x1) * 100}%`,
              height: `${(y2 - y1) * 100}%`,
              borderColor: color,
            }}
          >
            <span
              className="absolute -top-5 left-0 whitespace-nowrap rounded px-1 text-[10px] font-medium text-slate-900"
              style={{ backgroundColor: color }}
            >
              {d.canonical_class} {(d.confidence * 100).toFixed(0)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function DetectionsPanel({ sessionId }: { sessionId: string }) {
  const [batches, setBatches] = useState<FrameDetectionBatch[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState(0);

  const load = useCallback(() => {
    listDetections(sessionId, { pageSize: 100 })
      .then((b) => {
        setBatches(b);
        setSelected((s) => Math.min(s, Math.max(0, b.length - 1)));
      })
      .catch((e) => setError(e?.error?.message ?? "Failed to load detections"));
  }, [sessionId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <p className="mt-6 text-sm text-red-400">{error}</p>;
  if (!batches) return <p className="mt-6 text-sm text-slate-400">Loading detections…</p>;
  if (batches.length === 0)
    return (
      <p className="mt-6 text-sm text-slate-500">
        No detections recorded for this session yet.
      </p>
    );

  const current = batches[selected];
  const anyTest = batches.some((b) => b.is_test_provider);

  return (
    <div className="mt-8">
      <h2 className="mb-2 text-lg font-semibold">Detections</h2>

      {anyTest && (
        <div
          role="alert"
          className="mb-4 rounded border-2 border-amber-500 bg-amber-500/10 p-3 text-sm font-bold uppercase tracking-wide text-amber-300"
        >
          ⚠ Test provider — not real AI detection
          <p className="mt-1 text-xs font-normal normal-case text-amber-200/80">
            These boxes are deterministic placeholder output produced without any trained
            model. They are for infrastructure validation only and are meaningless as
            vehicle/pedestrian detections.
          </p>
        </div>
      )}

      {/* Frame selector */}
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
        <button
          className="rounded bg-slate-700 px-2 py-1 disabled:opacity-40"
          disabled={selected === 0}
          onClick={() => setSelected((s) => Math.max(0, s - 1))}
        >
          ← Prev
        </button>
        <span className="font-mono text-slate-300">
          frame {current.source_frame_index}
          {current.pts_seconds != null ? ` @ ${current.pts_seconds.toFixed(3)}s` : ""}
          {" "}({selected + 1}/{batches.length})
        </span>
        <button
          className="rounded bg-slate-700 px-2 py-1 disabled:opacity-40"
          disabled={selected >= batches.length - 1}
          onClick={() => setSelected((s) => Math.min(batches.length - 1, s + 1))}
        >
          Next →
        </button>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row">
        <BoxOverlay detections={current.detections} />

        <div className="flex-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left text-slate-400">
                <th className="py-1 pr-4">Class</th>
                <th className="py-1 pr-4">Confidence</th>
                <th className="py-1">Normalized bbox</th>
              </tr>
            </thead>
            <tbody>
              {current.detections.map((d, i) => (
                <tr key={i} className="border-b border-slate-800">
                  <td className="py-1 pr-4">
                    <span
                      className="mr-2 inline-block h-2 w-2 rounded-full align-middle"
                      style={{ backgroundColor: CLASS_COLORS[d.canonical_class] ?? "#94a3b8" }}
                    />
                    {d.canonical_class}
                  </td>
                  <td className="py-1 pr-4 font-mono">{(d.confidence * 100).toFixed(1)}%</td>
                  <td className="py-1 font-mono text-xs text-slate-400">
                    [{d.bbox.map((v) => v.toFixed(3)).join(", ")}]
                  </td>
                </tr>
              ))}
              {current.detections.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-2 text-slate-500">
                    No objects in this frame (empty result — not a failure).
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <dl className="mt-4 space-y-1 text-xs text-slate-400">
            <div>
              <dt className="inline text-slate-500">Provider: </dt>
              <dd className="inline font-mono">
                {current.provider_name}
                {current.provider_version ? `:${current.provider_version}` : ""}
                {current.is_test_provider ? " (TEST)" : ""}
              </dd>
            </div>
            <div>
              <dt className="inline text-slate-500">Taxonomy: </dt>
              <dd className="inline font-mono">{current.taxonomy_version}</dd>
            </div>
            {current.model_version_id && (
              <div>
                <dt className="inline text-slate-500">Model version: </dt>
                <dd className="inline font-mono">{current.model_version_id.slice(0, 8)}…</dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
}

"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ApiRequestError } from "@/lib/api";
import { VideoAsset, listVideos, uploadVideo } from "@/lib/videoApi";

function human(bytes: number): string {
  if (bytes > 1e9) return `${(bytes / 1e9).toFixed(2)} GB`;
  if (bytes > 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  return `${(bytes / 1e3).toFixed(0)} KB`;
}

export default function VideosPage() {
  const [videos, setVideos] = useState<VideoAsset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => {
    listVideos().then(setVideos).catch(() => setError("Failed to load videos"));
  }, []);

  useEffect(() => refresh(), [refresh]);

  async function onUpload(e: FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setError(null);
    setBusy(true);
    try {
      await uploadVideo(file);
      if (fileRef.current) fileRef.current.value = "";
      refresh();
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? `${err.error.code}: ${err.error.message}`
          : "Upload failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Videos</h1>
      {error && <p className="mb-3 rounded bg-red-950 px-3 py-2 text-sm text-red-300">{error}</p>}

      <form onSubmit={onUpload} className="mb-6 flex items-end gap-3 rounded-lg bg-panel p-4">
        <label className="text-sm">
          <span className="mb-1 block text-slate-400">Upload video file</span>
          <input ref={fileRef} type="file" accept="video/*" required
            className="text-sm text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-slate-700 file:px-3 file:py-1.5 file:text-slate-100" />
        </label>
        <button type="submit" disabled={busy}
          className="rounded bg-sky-600 px-4 py-2 text-sm hover:bg-sky-500 disabled:opacity-50">
          {busy ? "Uploading…" : "Upload"}
        </button>
      </form>

      <div className="overflow-x-auto rounded-lg bg-panel">
        <table className="w-full text-left text-sm">
          <thead className="text-slate-400">
            <tr>
              <th className="p-3">File</th>
              <th className="p-3">Status</th>
              <th className="p-3">Codec</th>
              <th className="p-3">Resolution</th>
              <th className="p-3">Size</th>
              <th className="p-3">Active</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {videos.map((v) => (
              <tr key={v.id} className="border-t border-slate-800">
                <td className="p-3">{v.original_filename || v.id.slice(0, 8)}</td>
                <td className="p-3">
                  <span className={v.validation_status === "valid" ? "text-emerald-400" : v.validation_status === "invalid" ? "text-red-400" : "text-amber-400"}>
                    {v.validation_status}
                  </span>
                </td>
                <td className="p-3">{v.codec || "—"}</td>
                <td className="p-3">{v.width ? `${v.width}×${v.height}` : "—"}</td>
                <td className="p-3">{human(v.size_bytes)}</td>
                <td className="p-3">{v.is_active ? "yes" : "no"}</td>
                <td className="p-3">
                  <Link href={`/admin/videos/${v.id}`} className="text-xs text-sky-300 hover:text-sky-200">
                    Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

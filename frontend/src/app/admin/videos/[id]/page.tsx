"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  VideoAsset,
  archiveVideo,
  deleteVideo,
  fetchThumbnailUrl,
  getVideo,
} from "@/lib/videoApi";
import { createSession } from "@/lib/processingApi";
import { useAuth } from "@/lib/auth";

const PROCESS_ROLES = ["system_admin", "traffic_admin", "traffic_operator"];

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [video, setVideo] = useState<VideoAsset | null>(null);
  const [thumb, setThumb] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const startProcessing = () => {
    setStarting(true);
    setError(null);
    createSession({ video_id: id, processor: "framecount", sampling: { mode: "every_frame" } })
      .then((s) => router.push(`/admin/processing/${s.id}`))
      .catch((e) => setError(e?.error?.message ?? "Failed to start processing"))
      .finally(() => setStarting(false));
  };

  const load = useCallback(() => {
    getVideo(id).then(setVideo).catch(() => setError("Failed to load video"));
  }, [id]);

  useEffect(() => load(), [load]);

  useEffect(() => {
    if (video?.has_thumbnail) {
      fetchThumbnailUrl(id).then(setThumb).catch(() => undefined);
    }
  }, [video, id]);

  if (error) return <p className="text-red-400">{error}</p>;
  if (!video) return <p className="text-slate-400">Loading…</p>;

  const rows: [string, string][] = [
    ["Filename", video.original_filename || "—"],
    ["Validation", video.validation_status + (video.error_code ? ` (${video.error_code})` : "")],
    ["Container", video.container_format || "—"],
    ["Codec", video.codec || "—"],
    ["Duration", video.duration_s ? `${video.duration_s.toFixed(2)} s` : "—"],
    ["Resolution", video.width ? `${video.width}×${video.height}` : "—"],
    ["FPS", video.fps ? video.fps.toFixed(2) : "—"],
    ["Frames", video.frame_count?.toString() ?? "—"],
    ["Checksum", video.checksum_sha256.slice(0, 16) + "…"],
    ["Active", video.is_active ? "yes" : "no"],
  ];

  return (
    <div>
      <button onClick={() => router.push("/admin/videos")} className="mb-4 text-sm text-slate-400 hover:text-slate-200">
        ← Videos
      </button>
      <h1 className="mb-4 text-xl font-semibold">{video.original_filename || video.id}</h1>
      <div className="flex flex-wrap gap-6">
        <div className="rounded-lg bg-panel p-4">
          {thumb ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={thumb} alt="thumbnail" className="max-w-xs rounded" />
          ) : (
            <div className="flex h-40 w-64 items-center justify-center text-slate-500">No thumbnail</div>
          )}
        </div>
        <table className="text-sm">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k} className="border-b border-slate-800">
                <td className="py-2 pr-6 text-slate-400">{k}</td>
                <td className="py-2">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 flex gap-3">
        {video.is_active && video.validation_status === "valid" &&
          PROCESS_ROLES.includes(user?.role ?? "") && (
          <button onClick={startProcessing} disabled={starting}
            className="rounded bg-sky-800 px-4 py-2 text-sm hover:bg-sky-700 disabled:opacity-50">
            {starting ? "Starting…" : "Start Processing"}
          </button>
        )}
        {video.is_active && (
          <button onClick={() => archiveVideo(id).then(load)}
            className="rounded bg-slate-700 px-4 py-2 text-sm hover:bg-slate-600">
            Archive
          </button>
        )}
        {user?.role === "system_admin" && (
          <button
            onClick={() => deleteVideo(id).then(() => router.push("/admin/videos"))}
            className="rounded bg-red-900 px-4 py-2 text-sm hover:bg-red-800">
            Delete
          </button>
        )}
      </div>
    </div>
  );
}

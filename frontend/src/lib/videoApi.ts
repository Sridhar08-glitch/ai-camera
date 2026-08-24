// Phase 4 video-management API helpers.
import { ApiRequestError, apiFetch, getAccessToken } from "./api";
import { config } from "./config";

export interface VideoAsset {
  id: string;
  original_filename: string;
  camera: string | null;
  source_type: string;
  size_bytes: number;
  checksum_sha256: string;
  container_format: string;
  codec: string;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  frame_count: number | null;
  validation_status: string;
  is_active: boolean;
  error_code: string;
  error_message: string;
  has_thumbnail: boolean;
  uploaded_at: string;
}

export const listVideos = () => apiFetch<VideoAsset[]>("/videos");
export const getVideo = (id: string) => apiFetch<VideoAsset>(`/videos/${id}`);
export const archiveVideo = (id: string) =>
  apiFetch<VideoAsset>(`/videos/${id}/archive`, { method: "POST" });
export const deleteVideo = (id: string) =>
  apiFetch<null>(`/videos/${id}`, { method: "DELETE" });

// Multipart upload — do NOT set Content-Type (browser sets the boundary).
export async function uploadVideo(
  file: File,
  cameraId?: string,
): Promise<VideoAsset> {
  const form = new FormData();
  form.append("file", file);
  if (cameraId) form.append("camera", cameraId);
  const token = getAccessToken();
  const res = await fetch(`${config.apiBaseUrl}/videos`, {
    method: "POST",
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new ApiRequestError(res.status, body?.error ?? { code: "error", message: `HTTP ${res.status}` });
  }
  return body.data as VideoAsset;
}

// Auth'd thumbnail: fetch bytes and return an object URL (<img> can't send auth headers).
export async function fetchThumbnailUrl(id: string): Promise<string> {
  const token = getAccessToken();
  const res = await fetch(`${config.apiBaseUrl}/videos/${id}/thumbnail`, {
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error("thumbnail unavailable");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// Phase 5 processing-session API helpers. No AI/detection — lifecycle only.
import { apiFetch } from "./api";

export interface ProcessingSession {
  id: string;
  video_id: string;
  camera_id: string | null;
  state: string;
  requested_action: string;
  processing_params: Record<string, unknown>;
  snapshot_hash: string;
  frames_total_estimate: number | null;
  frames_decoded: number;
  frames_processed: number;
  current_frame_index: number | null;
  current_pts_seconds: number | null;
  progress_percent: number | null;
  decode_fps: number | null;
  processing_fps: number | null;
  runtime_id: string;
  runtime_version: string;
  device: string;
  error_code: string;
  error_message: string;
  retry_of: string | null;
  retry_count: number;
  queued_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  last_heartbeat_at: string | null;
  created_at: string;
}

export interface SamplingParams {
  mode: string;
  n?: number;
  target_fps?: number;
}

export interface DetectorParams {
  model_version_id?: string; // "test" (deterministic TEST provider) or a model version id
  conf?: number;
  iou?: number;
}

export interface CreateSessionInput {
  video_id: string;
  sampling?: SamplingParams;
  processor?: string;
  device_preference?: string;
  detector?: DetectorParams;
}

// One detection in canonical normalized XYXY (resolution-independent, [0,1]).
export interface Detection {
  class_id: number;
  canonical_class: string;
  confidence: number;
  bbox: [number, number, number, number]; // normalized x1,y1,x2,y2
  bbox_format: string;
}

// One processed frame's detections + producing-provider identity.
export interface FrameDetectionBatch {
  id: string;
  session_id: string;
  source_frame_index: number;
  pts_seconds: number | null;
  provider_name: string;
  provider_version: string;
  is_test_provider: boolean; // true => deterministic TEST output, NOT real AI
  model_version_id: string | null;
  taxonomy_version: string;
  detection_count: number;
  detections: Detection[];
  created_at: string;
}

export interface RuntimeStatus {
  cv_runtime_available: boolean;
  heartbeat_age_seconds: number | null;
  gpu: {
    available: boolean;
    mode: string;
    detector: string;
    devices: {
      index: number;
      name: string;
      memory_total_mb: number | null;
      memory_free_mb: number | null;
      driver_version: string;
    }[];
  };
}

const BASE = "/processing-sessions";

export const listSessions = (videoId?: string) =>
  apiFetch<ProcessingSession[]>(`${BASE}${videoId ? `?video=${videoId}` : ""}`);

export const getSession = (id: string) => apiFetch<ProcessingSession>(`${BASE}/${id}`);

export const createSession = (input: CreateSessionInput) =>
  apiFetch<ProcessingSession>(BASE, { method: "POST", body: JSON.stringify(input) });

export const cancelSession = (id: string) =>
  apiFetch<ProcessingSession>(`${BASE}/${id}/cancel`, { method: "POST" });

export const stopSession = (id: string) =>
  apiFetch<ProcessingSession>(`${BASE}/${id}/stop`, { method: "POST" });

export const pauseSession = (id: string) =>
  apiFetch<ProcessingSession>(`${BASE}/${id}/pause`, { method: "POST" });

export const resumeSession = (id: string) =>
  apiFetch<ProcessingSession>(`${BASE}/${id}/resume`, { method: "POST" });

export const retrySession = (id: string) =>
  apiFetch<ProcessingSession>(`${BASE}/${id}/retry`, { method: "POST" });

export const getRuntimeStatus = () =>
  apiFetch<RuntimeStatus>("/processing/runtime-status");

// Phase 6: paginated per-frame detections for a session (read-only).
export const listDetections = (
  id: string,
  opts?: { frame?: number; fromTs?: number; toTs?: number; page?: number; pageSize?: number },
) => {
  const q = new URLSearchParams();
  if (opts?.frame != null) q.set("frame", String(opts.frame));
  if (opts?.fromTs != null) q.set("from_ts", String(opts.fromTs));
  if (opts?.toTs != null) q.set("to_ts", String(opts.toTs));
  if (opts?.page != null) q.set("page", String(opts.page));
  if (opts?.pageSize != null) q.set("page_size", String(opts.pageSize));
  const qs = q.toString();
  return apiFetch<FrameDetectionBatch[]>(`${BASE}/${id}/detections${qs ? `?${qs}` : ""}`);
};

export const getDetectionFrame = (id: string, frameIndex: number) =>
  apiFetch<FrameDetectionBatch>(`${BASE}/${id}/detections/${frameIndex}`);

export const TERMINAL_STATES = ["completed", "failed", "cancelled", "stopped"];
export const isTerminal = (s: string) => TERMINAL_STATES.includes(s);

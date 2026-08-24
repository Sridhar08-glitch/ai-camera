// Central access to browser-exposed configuration. No secrets.
const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const config = {
  apiBaseUrl,
  // Health endpoints live at /api/ (one level above /api/v1).
  apiRoot: apiBaseUrl.replace(/\/v1$/, ""),
  wsUrl: process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws",
};

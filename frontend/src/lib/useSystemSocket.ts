"use client";

// Connects to the authenticated system heartbeat WebSocket using the in-memory
// access token via the `access_token` subprotocol (consistent with REST auth).

import { useEffect, useState } from "react";
import { config } from "./config";
import { getAccessToken } from "./api";

type WsStatus = "connecting" | "connected" | "closed";

export function useSystemSocket(enabled: boolean) {
  const [status, setStatus] = useState<WsStatus>("closed");
  const [lastHeartbeat, setLastHeartbeat] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const token = getAccessToken();
    if (!token) return;

    setStatus("connecting");
    const ws = new WebSocket(`${config.wsUrl}/system/`, ["access_token", token]);

    ws.onopen = () => setStatus("connected");
    ws.onclose = () => setStatus("closed");
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "heartbeat" || msg.type === "welcome") {
          setLastHeartbeat(msg.ts);
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    return () => ws.close();
  }, [enabled]);

  return { status, lastHeartbeat };
}

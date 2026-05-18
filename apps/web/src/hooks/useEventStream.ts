import { useCallback, useEffect, useRef } from "react";
import type { WSEvent } from "../lib/types";

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "";

export function useEventStream(
  sessionId: string | null,
  onEvent: (event: WSEvent) => void
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback((sid: string) => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const base = WS_BASE || `${protocol}://${window.location.host}`;
    const ws = new WebSocket(`${base}/ws/events?session_id=${sid}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data as string) as WSEvent;
        onEventRef.current(event);
      } catch {
        /* ignore malformed */
      }
    };

    ws.onerror = () => ws.close();
    ws.onclose = () => {
      // reconnect if session still active
      if (wsRef.current === ws) {
        setTimeout(() => connect(sid), 2000);
      }
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    connect(sessionId);
    return () => {
      const ws = wsRef.current;
      wsRef.current = null;
      ws?.close();
    };
  }, [sessionId, connect]);
}

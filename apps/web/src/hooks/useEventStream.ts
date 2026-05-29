import { useCallback, useEffect, useRef } from "react";
import type { WSEvent } from "../lib/types";

const WS_BASE = import.meta.env.VITE_WS_BASE ?? "";

export function useEventStream(
  sessionId: string | null,
  onEvent: (event: WSEvent) => void,
  onReconnect?: () => void,
) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  const onReconnectRef = useRef(onReconnect);
  const activeRef = useRef(false);
  const attemptRef = useRef(0);
  // Store pending reconnect timer so it can be cancelled on cleanup or session-id change.
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Skip onReconnect on the first successful open — caller already loads initial state on mount
  const hasConnectedRef = useRef(false);

  onEventRef.current = onEvent;
  onReconnectRef.current = onReconnect;

  const connect = useCallback((sid: string) => {
    // Cancel any pending reconnect before opening a new connection.
    // Without this, a stale timer from an old sessionId can fire after the new
    // effect sets activeRef=true and call connect(oldSid), creating a second socket.
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      const old = wsRef.current;
      old.onclose = null;
      old.close();
    }

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const base = WS_BASE || `${protocol}://${window.location.host}`;
    const ws = new WebSocket(`${base}/ws/events?session_id=${sid}`);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      if (hasConnectedRef.current) onReconnectRef.current?.();
      hasConnectedRef.current = true;
    };

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data as string) as WSEvent;
        onEventRef.current(event);
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onerror = () => ws.close();

    ws.onclose = () => {
      if (!activeRef.current) return;
      const attempt = ++attemptRef.current;
      const delay = Math.min(1000 * Math.pow(2, attempt - 1) + Math.random() * 500, 30_000);
      // Store handle so cleanup can cancel it.
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        if (activeRef.current) connect(sid);
      }, delay);
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    activeRef.current = true;
    hasConnectedRef.current = false;
    attemptRef.current = 0;
    connect(sessionId);
    return () => {
      activeRef.current = false;
      // Cancel pending reconnect so a stale timer can't open a second socket.
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [sessionId, connect]);
}

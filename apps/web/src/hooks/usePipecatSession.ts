import DailyIframe, { type DailyCall } from "@daily-co/daily-js";
import { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";
import type { VoiceSessionStatus } from "../lib/types";

export function usePipecatSession() {
  const [status, setStatus] = useState<VoiceSessionStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const callRef = useRef<DailyCall | null>(null);

  const start = useCallback(async () => {
    setStatus("connecting");
    setError(null);
    try {
      const { session_id, room_url, token } = await api.voice.createSession();
      setSessionId(session_id);

      const call = DailyIframe.createCallObject({
        audioSource: true,
        videoSource: false,
      });
      callRef.current = call;

      call.on("left-meeting", () => {
        setStatus("idle");
        setSessionId(null);
      });
      call.on("error", (e) => {
        setError(e?.errorMsg ?? "Daily error");
        setStatus("error");
      });

      await call.join({ url: room_url, token });
      setStatus("active");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start session";
      setError(msg);
      setStatus("error");
    }
  }, []);

  const stop = useCallback(async () => {
    setStatus("disconnecting");
    try {
      if (callRef.current) {
        await callRef.current.leave();
        callRef.current.destroy();
        callRef.current = null;
      }
      if (sessionId) {
        await api.voice.endSession(sessionId).catch(() => {});
      }
    } finally {
      setStatus("idle");
      setSessionId(null);
    }
  }, [sessionId]);

  const toggleMic = useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    call.setLocalAudio(!call.localAudio());
  }, []);

  return { status, sessionId, error, start, stop, toggleMic };
}

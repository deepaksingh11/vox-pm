import DailyIframe, { type DailyCall } from "@daily-co/daily-js";
import { useCallback, useRef, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "./useStore";
import type { VoiceSessionStatus } from "../lib/types";

export function usePipecatSession() {
  const [status, setStatus] = useState<VoiceSessionStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const callRef = useRef<DailyCall | null>(null);
  const clearAgentState = useStore((s) => s.clearAgentState);

  const start = useCallback(async () => {
    setStatus("connecting");
    setError(null);
    setMuted(false);
    try {
      // Preflight: surface mic permission before Daily runs so errors are readable
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
      } catch (permErr) {
        const name = permErr instanceof Error ? permErr.name : "Unknown";
        throw new Error(
          name === "NotAllowedError"
            ? "Microphone permission denied. Allow mic access and retry."
            : name === "NotFoundError"
              ? "No microphone found. Connect a mic and retry."
              : `Mic unavailable: ${name}`
        );
      }

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
        setMuted(false);
      });
      call.on("error", (e) => {
        setError(e?.errorMsg ?? "Daily error");
        setStatus("error");
      });
      call.on("camera-error", (e) => {
        const msg = e?.errorMsg ?? "unknown";
        console.error("[Daily] camera-error:", msg);
        setError(`Mic unavailable: ${msg}`);
      });
      call.on("nonfatal-error", (e) => {
        console.warn("[Daily] nonfatal-error:", e?.errorMsg);
      });
      call.on("track-started", (e) => {
        if (e?.participant?.local && e?.track?.kind === "audio") {
          console.info("[Daily] local audio track published — mic active");
        }
      });
      call.on("participant-updated", (e) => {
        if (!e?.participant?.local) return;
        const audioState = e.participant.tracks?.audio?.state;
        console.info("[Daily] local audio.state:", audioState);
        // Sync muted from Daily truth — covers OS-level revocations
        const nowMuted = audioState === "off" || audioState === "blocked";
        setMuted(nowMuted);
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
      setMuted(false);
      clearAgentState();
    }
  }, [sessionId, clearAgentState]);

  const toggleMic = useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    const isActive = call.localAudio(); // true = mic on (not muted)
    call.setLocalAudio(!isActive);
    setMuted(isActive); // was active → now muting; was muted → now unmuting
  }, []);

  return { status, sessionId, error, muted, start, stop, toggleMic };
}

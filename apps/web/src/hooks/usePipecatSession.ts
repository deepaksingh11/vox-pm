import DailyIframe, { type DailyCall } from "@daily-co/daily-js";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, clientId, HttpError } from "../lib/api";
import { useStore } from "./useStore";
import type { VoiceSessionStatus } from "../lib/types";

// A hard page refresh can tear down React before the unmount cleanup's async
// DELETE /session call completes, leaving the backend's in-memory session
// marked active. The next create then 409s forever — retry alone can't fix a
// server-side stuck state. Self-heal: clear the stale session, then retry once.
async function createSessionWithStaleRetry() {
  try {
    return await api.voice.createSession();
  } catch (err) {
    if (err instanceof HttpError && err.status === 409) {
      await api.voice.endSession(clientId).catch(() => {});
      return await api.voice.createSession();
    }
    throw err;
  }
}

export function usePipecatSession() {
  const [status, setStatus] = useState<VoiceSessionStatus>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const callRef = useRef<DailyCall | null>(null);
  // Track session id in a ref so stop() always reads the current value even
  // if called before setSessionId()'s state flush has propagated.
  const sessionIdRef = useRef<string | null>(null);
  // Status ref for start() idempotency guard — avoids adding status to deps.
  const statusRef = useRef<VoiceSessionStatus>("idle");
  const clearAgentState = useStore((s) => s.clearAgentState);

  /** Sync status state + ref together. */
  const _setStatus = useCallback((s: VoiceSessionStatus) => {
    statusRef.current = s;
    setStatus(s);
  }, []);

  // Unmount cleanup: destroy any live Daily call so the mic is released.
  useEffect(() => {
    return () => {
      const c = callRef.current;
      if (c) {
        callRef.current = null;
        c.leave().catch(() => {});
        c.destroy();
      }
    };
  }, []);

  const start = useCallback(async () => {
    // Idempotency guard: bail if already connecting, active, or disconnecting.
    if (statusRef.current !== "idle" && statusRef.current !== "error") return;
    _setStatus("connecting");
    setError(null);
    setMuted(false);
    try {
      // Preflight: surface mic permission before Daily runs so errors are readable.
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

      const { session_id, room_url, token } = await createSessionWithStaleRetry();
      // Set ref immediately (before any await) so stop() can read it even if
      // the state flush hasn't propagated yet.
      sessionIdRef.current = session_id;
      setSessionId(session_id);

      const call = DailyIframe.createCallObject({
        audioSource: true,
        videoSource: false,
      });
      callRef.current = call;

      call.on("left-meeting", () => {
        sessionIdRef.current = null;
        _setStatus("idle");
        setSessionId(null);
        setMuted(false);
      });
      call.on("error", (e) => {
        setError(e?.errorMsg ?? "Daily error");
        _setStatus("error");
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
        // Sync muted from Daily truth — covers OS-level revocations.
        const nowMuted = audioState === "off" || audioState === "blocked";
        setMuted(nowMuted);
      });

      await call.join({ url: room_url, token });
      _setStatus("active");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to start session";
      setError(msg);
      _setStatus("error");
    }
  }, [_setStatus]);

  const stop = useCallback(async () => {
    _setStatus("disconnecting");
    // Null callRef before any await so nothing else can grab a half-dead call.
    const call = callRef.current;
    callRef.current = null;
    // Read ref, not state: state may be stale if stop() is called before
    // React flushes the setSessionId update from start().
    const sid = sessionIdRef.current;
    sessionIdRef.current = null;
    try {
      if (call) {
        // Always destroy even if leave() rejects — keeps callRef nulled.
        try { await call.leave(); } catch { /* ignore */ }
        try { call.destroy(); } catch { /* ignore */ }
      }
      if (sid) {
        await api.voice.endSession(sid).catch(() => {});
      }
    } finally {
      _setStatus("idle");
      setSessionId(null);
      setMuted(false);
      clearAgentState();
    }
  }, [_setStatus, clearAgentState]);

  const toggleMic = useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    const isActive = call.localAudio(); // true = mic on (not muted)
    call.setLocalAudio(!isActive);
    setMuted(isActive); // was active → now muting; was muted → now unmuting
  }, []);

  return { status, sessionId, error, muted, start, stop, toggleMic };
}

import { Mic, MicOff, PhoneOff, Loader2, Radio } from "lucide-react";
import type { VoiceSessionStatus } from "../lib/types";
import { cn } from "../lib/utils";

interface Props {
  status: VoiceSessionStatus;
  isMuted: boolean;
  onStart: () => void;
  onStop: () => void;
  onToggleMic: () => void;
  error: string | null;
}

const statusLabel: Record<VoiceSessionStatus, string> = {
  idle:          "Start session",
  connecting:    "Connecting…",
  active:        "End session",
  error:         "Retry",
  disconnecting: "Disconnecting…",
};

export function VoiceControl({ status, isMuted, onStart, onStop, onToggleMic, error }: Props) {
  const isActive = status === "active";
  const isBusy   = status === "connecting" || status === "disconnecting";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          onClick={isActive ? onStop : onStart}
          disabled={isBusy}
          className={cn(
            "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-sm",
            isActive
              ? "bg-destructive text-white hover:bg-destructive/90"
              : "bg-primary text-primary-foreground hover:bg-primary/90",
            isBusy && "opacity-50 cursor-not-allowed"
          )}
        >
          {isBusy ? (
            <Loader2 size={15} className="animate-spin" />
          ) : isActive ? (
            <PhoneOff size={15} />
          ) : (
            <Radio size={15} />
          )}
          {statusLabel[status]}
        </button>

        {isActive && (
          <button
            onClick={onToggleMic}
            className={cn(
              "p-2.5 rounded-xl transition-colors",
              isMuted
                ? "bg-destructive/10 text-destructive hover:bg-destructive/20"
                : "bg-muted hover:bg-muted/80 text-foreground"
            )}
            title={isMuted ? "Unmute mic" : "Mute mic"}
          >
            {isMuted ? <MicOff size={15} /> : <Mic size={15} />}
          </button>
        )}
      </div>

      {isActive && (
        <div className="flex items-center justify-center gap-1 h-6">
          {[0.4, 0.7, 1, 0.7, 0.9, 0.5, 0.8, 0.6, 1, 0.4].map((scale, i) => (
            <div
              key={i}
              className={cn("w-1 rounded-full", isMuted ? "bg-muted-foreground/30" : "bg-primary")}
              style={{
                height: `${scale * 20}px`,
                animation: isMuted ? "none" : "bar-bounce 1s ease-in-out infinite",
                animationDelay: `${i * 0.08}s`,
              }}
            />
          ))}
        </div>
      )}

      {error && (
        <p className="text-xs text-destructive text-center">{error}</p>
      )}
    </div>
  );
}

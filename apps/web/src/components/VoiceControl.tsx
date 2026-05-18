import { Mic, PhoneOff, Loader2, Radio } from "lucide-react";
import type { VoiceSessionStatus } from "../lib/types";
import { cn } from "../lib/utils";

interface Props {
  status: VoiceSessionStatus;
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

export function VoiceControl({ status, onStart, onStop, onToggleMic, error }: Props) {
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
            className="p-2.5 rounded-xl bg-muted hover:bg-muted/80 text-foreground transition-colors"
            title="Toggle mic"
          >
            <Mic size={15} />
          </button>
        )}
      </div>

      {isActive && (
        <div className="flex items-center justify-center gap-1 h-6">
          {[0.4, 0.7, 1, 0.7, 0.9, 0.5, 0.8, 0.6, 1, 0.4].map((scale, i) => (
            <div
              key={i}
              className="w-1 rounded-full bg-primary"
              style={{
                height: `${scale * 20}px`,
                animation: "bar-bounce 1s ease-in-out infinite",
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

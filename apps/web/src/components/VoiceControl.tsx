import { Mic, Phone, PhoneOff, Loader2 } from "lucide-react";
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
  idle: "Start session",
  connecting: "Connecting…",
  active: "Active",
  error: "Error",
  disconnecting: "Disconnecting…",
};

export function VoiceControl({ status, onStart, onStop, onToggleMic, error }: Props) {
  const isActive = status === "active";
  const isBusy = status === "connecting" || status === "disconnecting";

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="flex items-center gap-3">
        <button
          onClick={isActive ? onStop : onStart}
          disabled={isBusy}
          className={cn(
            "flex items-center gap-2 px-5 py-2.5 rounded-full font-semibold text-sm transition-all",
            isActive
              ? "bg-red-600 hover:bg-red-700 text-white"
              : "bg-brand-500 hover:bg-brand-600 text-white",
            isBusy && "opacity-50 cursor-not-allowed"
          )}
        >
          {isBusy ? (
            <Loader2 size={16} className="animate-spin" />
          ) : isActive ? (
            <PhoneOff size={16} />
          ) : (
            <Phone size={16} />
          )}
          {statusLabel[status]}
        </button>

        {isActive && (
          <button
            onClick={onToggleMic}
            className="p-2.5 rounded-full bg-slate-700 hover:bg-slate-600 transition-colors"
            title="Toggle mic"
          >
            <Mic size={16} />
          </button>
        )}
      </div>

      {/* Pulse ring when active */}
      {isActive && (
        <div className="flex items-center gap-1.5">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="w-1 bg-brand-500 rounded-full animate-pulse"
              style={{
                height: `${8 + Math.abs(2 - i) * 6}px`,
                animationDelay: `${i * 0.1}s`,
              }}
            />
          ))}
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 max-w-xs text-center">{error}</p>
      )}
    </div>
  );
}

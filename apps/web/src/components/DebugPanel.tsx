import { useState } from "react";
import { useStore } from "../hooks/useStore";

export function DebugPanel() {
  const [open, setOpen] = useState(false);
  const debugEvents = useStore((s) => s.debugEvents);

  if (new URLSearchParams(window.location.search).get("debug") !== "1") return null;

  return (
    <div className="border-t border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-2 flex items-center justify-between text-[11px] font-semibold text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
      >
        Debug events ({debugEvents.length})
        <span className="text-muted-foreground/60">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="h-48 overflow-y-auto bg-muted/20 px-3 py-2 font-mono text-[10px] space-y-0.5">
          {debugEvents.length === 0 ? (
            <p className="text-muted-foreground/50">No events yet</p>
          ) : (
            [...debugEvents].reverse().map((e, i) => (
              <div key={i} className="leading-relaxed">
                <span className="text-muted-foreground/50">
                  {new Date(e.ts).toISOString().slice(11, 23)}
                </span>{" "}
                <span className="text-primary font-semibold">[{e.type}]</span>{" "}
                <span className="text-muted-foreground">
                  {JSON.stringify(e.data).slice(0, 120)}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

import { useStore } from "../hooks/useStore";

export function LiveTranscript() {
  const partial  = useStore((s) => s.partialTranscript);
  const final    = useStore((s) => s.finalTranscript);
  const thinking = useStore((s) => s.agentThinking);

  if (!partial && !final && !thinking) return null;

  return (
    <div className="bg-muted/60 border border-border rounded-xl px-4 py-3 text-sm min-h-[52px] space-y-1">
      {final && (
        <p className="text-foreground leading-relaxed">
          <span className="text-muted-foreground text-xs font-medium mr-1.5">you</span>
          {final}
        </p>
      )}
      {partial && (
        <p className="text-muted-foreground italic leading-relaxed">
          <span className="text-muted-foreground/60 text-xs mr-1.5">…</span>
          {partial}
        </p>
      )}
      {thinking && !partial && (
        <p className="text-primary text-xs font-medium animate-pulse">Agent processing…</p>
      )}
    </div>
  );
}

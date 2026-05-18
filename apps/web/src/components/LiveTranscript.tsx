import { useStore } from "../hooks/useStore";

export function LiveTranscript() {
  const partial = useStore((s) => s.partialTranscript);
  const final = useStore((s) => s.finalTranscript);
  const thinking = useStore((s) => s.agentThinking);

  if (!partial && !final && !thinking) return null;

  return (
    <div className="bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3 text-sm min-h-[52px]">
      {final && (
        <p className="text-slate-200 leading-relaxed">
          <span className="text-slate-500 text-xs mr-1">you:</span>
          {final}
        </p>
      )}
      {partial && (
        <p className="text-slate-400 italic leading-relaxed">
          <span className="text-slate-500 text-xs mr-1">…</span>
          {partial}
        </p>
      )}
      {thinking && !partial && (
        <p className="text-brand-500 text-xs animate-pulse">Agent processing…</p>
      )}
    </div>
  );
}

import { MessageCircleQuestion, X } from "lucide-react";
import { useStore } from "../hooks/useStore";

export function ClarificationPrompt() {
  const clarification      = useStore((s) => s.clarification);
  const clearClarification = useStore((s) => s.clearClarification);

  if (!clarification) return null;

  return (
    <div className="bg-accent border border-border rounded-xl px-4 py-3 flex items-start gap-3" style={{ animation: "fade-in 0.2s ease-out" }}>
      <MessageCircleQuestion size={16} className="text-primary shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-accent-foreground">{clarification.question}</p>
        {clarification.candidates.length > 0 && (
          <ul className="mt-2 space-y-1">
            {clarification.candidates.map((c, i) => (
              <li key={c} className="text-xs text-accent-foreground/80 flex items-center gap-1.5">
                <span className="w-4 h-4 rounded-full bg-primary/20 flex items-center justify-center text-[10px] font-bold text-primary shrink-0">
                  {i + 1}
                </span>
                {c}
              </li>
            ))}
          </ul>
        )}
        <p className="text-[11px] text-muted-foreground mt-2">Speak your answer to continue</p>
      </div>
      <button
        onClick={clearClarification}
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        <X size={14} />
      </button>
    </div>
  );
}

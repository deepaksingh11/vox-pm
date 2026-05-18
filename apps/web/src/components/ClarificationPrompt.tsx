import { MessageCircleQuestion, X } from "lucide-react";
import { useStore } from "../hooks/useStore";

export function ClarificationPrompt() {
  const clarification = useStore((s) => s.clarification);
  const clearClarification = useStore((s) => s.clearClarification);

  if (!clarification) return null;

  return (
    <div className="bg-purple-950/80 border border-purple-700 rounded-xl px-4 py-3 flex items-start gap-3">
      <MessageCircleQuestion size={18} className="text-purple-400 shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="text-sm text-purple-100 font-medium">{clarification.question}</p>
        {clarification.candidates.length > 0 && (
          <ul className="mt-1.5 space-y-1">
            {clarification.candidates.map((c, i) => (
              <li key={i} className="text-xs text-purple-300">
                • {c}
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-purple-500 mt-2">Speak your answer to continue</p>
      </div>
      <button
        onClick={clearClarification}
        className="text-purple-600 hover:text-purple-400"
      >
        <X size={14} />
      </button>
    </div>
  );
}

import { formatDistanceToNow } from "date-fns";
import { useStore } from "../hooks/useStore";
import { cn } from "../lib/utils";
import type { ActionEntry } from "../lib/types";

const typeColor: Partial<Record<ActionEntry["type"], string>> = {
  "project.created": "text-emerald-400",
  "project.updated": "text-sky-400",
  "project.deleted": "text-red-400",
  "task.created": "text-emerald-400",
  "task.updated": "text-sky-400",
  "task.deleted": "text-red-400",
  "task.moved": "text-amber-400",
  "clarification.ask": "text-purple-400",
};

function ActionItem({ action }: { action: ActionEntry }) {
  const color = typeColor[action.type] ?? "text-slate-400";
  return (
    <li className="flex items-start gap-2 py-1.5 border-b border-slate-800 last:border-0">
      <span className={cn("text-xs mt-0.5 shrink-0 font-mono", color)}>
        {action.type.split(".")[0][0].toUpperCase()}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-200 truncate">{action.summary}</p>
        <p className="text-xs text-slate-500">
          {formatDistanceToNow(new Date(action.ts), { addSuffix: true })}
        </p>
      </div>
    </li>
  );
}

export function ActionFeed() {
  const actions = useStore((s) => s.actions);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 h-full overflow-y-auto scrollbar-thin">
      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
        Agent Actions
      </h3>
      {actions.length === 0 ? (
        <p className="text-xs text-slate-600 text-center mt-8">
          Actions appear here as the agent works
        </p>
      ) : (
        <ul>
          {actions.map((a) => (
            <ActionItem key={a.id} action={a} />
          ))}
        </ul>
      )}
    </div>
  );
}

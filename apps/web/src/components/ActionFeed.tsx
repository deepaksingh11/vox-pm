import { formatDistanceToNow } from "date-fns";
import { useStore } from "../hooks/useStore";
import { cn } from "../lib/utils";
import type { ActionEntry } from "../lib/types";

const typeConfig: Partial<Record<ActionEntry["type"], { dot: string; label: string }>> = {
  "project.created":   { dot: "bg-emerald-500", label: "Created project" },
  "project.updated":   { dot: "bg-sky-500",     label: "Updated project" },
  "project.deleted":   { dot: "bg-red-500",      label: "Deleted project" },
  "task.created":      { dot: "bg-emerald-500",  label: "Created task"   },
  "task.updated":      { dot: "bg-sky-500",      label: "Updated task"   },
  "task.deleted":      { dot: "bg-red-500",       label: "Deleted task"   },
  "task.moved":        { dot: "bg-amber-500",     label: "Moved task"     },
  "clarification.ask": { dot: "bg-violet-500",   label: "Asked clarification" },
};

function ActionItem({ action }: { action: ActionEntry }) {
  const cfg = typeConfig[action.type];
  return (
    <li className="flex items-start gap-3 py-2.5 border-b border-border/60 last:border-0" style={{ animation: "fade-in 0.2s ease-out" }}>
      <div className="shrink-0 mt-1.5">
        <div className={cn("w-1.5 h-1.5 rounded-full", cfg?.dot ?? "bg-muted-foreground")} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-muted-foreground">{cfg?.label ?? action.type}</p>
        <p className="text-sm text-foreground truncate mt-0.5">{action.summary}</p>
        <p className="text-[11px] text-muted-foreground/60 mt-0.5">
          {formatDistanceToNow(new Date(action.ts), { addSuffix: true })}
        </p>
      </div>
    </li>
  );
}

export function ActionFeed() {
  const actions = useStore((s) => s.actions);

  return (
    <div className="h-full flex flex-col">
      <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-3">
        Agent Actions
      </h3>
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {actions.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-xs text-muted-foreground/50 text-center">Actions appear here as the agent works</p>
          </div>
        ) : (
          <ul>
            {actions.map((a) => (
              <ActionItem key={a.id} action={a} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

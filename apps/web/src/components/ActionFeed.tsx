import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { useStore } from "../hooks/useStore";
import { cn } from "../lib/utils";
import type { ActionEntry } from "../lib/types";

const typeConfig: Partial<Record<ActionEntry["type"], { dot: string; label: string }>> = {
  "tool.started": { dot: "bg-muted-foreground/50", label: "Tool calling…" },
  "tool.completed": { dot: "bg-emerald-500 dark:bg-emerald-400", label: "Tool completed" },
  "tool.failed": { dot: "bg-red-500 dark:bg-red-400", label: "Tool failed" },
  "project.created": { dot: "bg-emerald-500 dark:bg-emerald-400", label: "Project created" },
  "project.updated": { dot: "bg-sky-500 dark:bg-sky-400", label: "Project updated" },
  "project.deleted": { dot: "bg-red-500 dark:bg-red-400", label: "Project deleted" },
  "task.created": { dot: "bg-emerald-500 dark:bg-emerald-400", label: "Task created" },
  "task.updated": { dot: "bg-sky-500 dark:bg-sky-400", label: "Task updated" },
  "task.deleted": { dot: "bg-red-500 dark:bg-red-400", label: "Task deleted" },
  "task.moved": { dot: "bg-amber-500 dark:bg-amber-400", label: "Task moved" },
  "clarification.ask": { dot: "bg-violet-500 dark:bg-violet-400", label: "Clarification asked" },
};

// L3: tick so formatDistanceToNow updates without a full page re-render
function useTick(intervalMs: number) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
}

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
          {(() => { try { return formatDistanceToNow(new Date(action.ts), { addSuffix: true }); } catch { return ""; } })()}
        </p>
      </div>
    </li>
  );
}

export function ActionFeed() {
  const actions = useStore((s) => s.actions);
  useTick(60_000);

  return (
    <div className="flex flex-col">
      <h3 className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-3 sticky top-0 bg-card py-1">
        Activity feed
      </h3>
      {actions.length === 0 ? (
        <div className="flex items-center justify-center h-32">
          <p className="text-xs text-muted-foreground/50 text-center">Activity appears here as you or the agent make changes</p>
        </div>
      ) : (
        <ul aria-live="polite" aria-label="Activity feed">
          {actions.map((a) => (
            <ActionItem key={a.id} action={a} />
          ))}
        </ul>
      )}
    </div>
  );
}

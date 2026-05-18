import { AlertCircle, Calendar, Bell, CheckCircle2, Circle } from "lucide-react";
import { format } from "date-fns";
import type { Task } from "../lib/types";
import { cn } from "../lib/utils";

interface Props {
  task: Task;
  index: number;
}

export function TaskRow({ task, index }: Props) {
  const isDone = task.status === "done";

  return (
    <div
      className={cn(
        "flex items-start gap-3 px-4 py-3 transition-colors group hover:bg-muted/50",
        isDone && "opacity-60"
      )}
    >
      <div className="shrink-0 mt-0.5">
        {isDone ? (
          <CheckCircle2 size={15} className="text-emerald-500" />
        ) : (
          <Circle size={15} className="text-muted-foreground/40 group-hover:text-muted-foreground/60 transition-colors" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] text-muted-foreground/40 font-mono tabular-nums">{index}</span>
          <span className={cn(
            "text-sm font-medium",
            isDone ? "line-through text-muted-foreground" : "text-foreground"
          )}>
            {task.title}
          </span>
          {task.urgent && (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-destructive bg-destructive/10 px-1.5 py-0.5 rounded-full">
              <AlertCircle size={9} />
              urgent
            </span>
          )}
        </div>

        {task.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{task.description}</p>
        )}

        {(task.due_at || task.reminder_at) && (
          <div className="flex items-center gap-3 mt-1.5">
            {task.due_at && (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Calendar size={10} />
                {format(new Date(task.due_at), "MMM d")}
              </span>
            )}
            {task.reminder_at && (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Bell size={10} />
                {format(new Date(task.reminder_at), "MMM d, h:mma")}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

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
        "flex items-start gap-3 px-3 py-2.5 rounded-lg transition-colors",
        "hover:bg-slate-800/50 group",
        isDone && "opacity-50"
      )}
    >
      <div className="shrink-0 mt-0.5">
        {isDone ? (
          <CheckCircle2 size={15} className="text-emerald-500" />
        ) : (
          <Circle size={15} className="text-slate-600" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-600 font-mono">[{index}]</span>
          <span className={cn("text-sm", isDone ? "line-through text-slate-500" : "text-slate-200")}>
            {task.title}
          </span>
          {task.urgent && (
            <span className="flex items-center gap-0.5 text-xs text-red-400 font-medium">
              <AlertCircle size={10} />
              urgent
            </span>
          )}
        </div>
        {task.description && (
          <p className="text-xs text-slate-500 mt-0.5 truncate">{task.description}</p>
        )}
        <div className="flex items-center gap-3 mt-1">
          {task.due_at && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Calendar size={10} />
              {format(new Date(task.due_at), "MMM d")}
            </span>
          )}
          {task.reminder_at && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <Bell size={10} />
              {format(new Date(task.reminder_at), "MMM d, h:mma")}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

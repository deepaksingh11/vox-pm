import React from "react";
import { AlertCircle, Calendar, Bell, MoreHorizontal, Loader2, Ban, XCircle } from "lucide-react";
import { format, isValid } from "date-fns";

function safeFormat(val: string | null | undefined, fmt: string): string | null {
  if (!val) return null;
  const d = new Date(val);
  return isValid(d) ? format(d, fmt) : null;
}
import type { Task } from "../lib/types";
import { cn } from "../lib/utils";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useStore } from "../hooks/useStore";

interface Props {
  task: Task;
  index: number;
}

const STATUS_BADGE: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
  in_progress: {
    label: "In progress",
    className: "text-blue-600 bg-blue-500/10",
    icon: <Loader2 size={9} className="animate-spin" />,
  },
  blocked: {
    label: "Blocked",
    className: "text-orange-600 bg-orange-500/10",
    icon: <Ban size={9} />,
  },
  cancelled: {
    label: "Cancelled",
    className: "text-muted-foreground bg-muted",
    icon: <XCircle size={9} />,
  },
};

export function TaskRow({ task, index: _index }: Props) {
  const isDone = task.status === "done";
  const toggleTaskDone = useStore((s) => s.toggleTaskDone);
  const deleteTask = useStore((s) => s.deleteTask);

  return (
    <div className="flex items-start gap-3 px-5 py-3 transition-colors group hover:bg-muted/40">
      <div className="shrink-0 mt-0.5 pt-px">
        <Checkbox
          checked={isDone}
          onCheckedChange={() => toggleTaskDone(task.id)}
          className="rounded-full border-muted-foreground/30 data-[state=checked]:bg-emerald-500 data-[state=checked]:border-emerald-500"
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={cn(
              "text-sm font-medium",
              isDone ? "line-through text-muted-foreground" : "text-foreground"
            )}
          >
            {task.title}
          </span>
          {task.urgent && (
            <span className="inline-flex items-center gap-0.5 text-[10px] font-semibold text-destructive bg-destructive/10 px-1.5 py-0.5 rounded-full">
              <AlertCircle size={9} />
              urgent
            </span>
          )}
          {STATUS_BADGE[task.status] && (
            <span className={cn("inline-flex items-center gap-0.5 text-[10px] font-semibold px-1.5 py-0.5 rounded-full", STATUS_BADGE[task.status].className)}>
              {STATUS_BADGE[task.status].icon}
              {STATUS_BADGE[task.status].label}
            </span>
          )}
        </div>

        {task.description && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{task.description}</p>
        )}

        {(task.due_at || task.reminder_at) && (
          <div className="flex items-center gap-3 mt-1.5">
            {task.due_at && safeFormat(task.due_at, "dd MMM yyyy") && (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Calendar size={10} />
                {safeFormat(task.due_at, "dd MMM yyyy")}
              </span>
            )}
            {task.reminder_at && safeFormat(task.reminder_at, "dd MMM yyyy, h:mma") && (
              <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                <Bell size={10} />
                {safeFormat(task.reminder_at, "dd MMM yyyy, h:mma")}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Hover-reveal delete */}
      <div className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center justify-center w-6 h-6 rounded hover:bg-accent text-muted-foreground">
              <MoreHorizontal size={13} />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-36">
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => deleteTask(task.id)}
            >
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}

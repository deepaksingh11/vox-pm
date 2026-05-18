import { FolderOpen, ChevronRight } from "lucide-react";
import type { Project, Task } from "../lib/types";
import { TaskRow } from "./TaskRow";

interface Props {
  project: Project;
  tasks: Task[];
}

export function ProjectCard({ project, tasks }: Props) {
  const open = tasks.filter((t) => t.status === "open");
  const done = tasks.filter((t) => t.status === "done");

  return (
    <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm hover:shadow-md transition-all" style={{ animation: "fade-in 0.2s ease-out" }}>
      <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-muted/40">
        <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <FolderOpen size={14} className="text-primary" />
        </div>
        <h2 className="font-semibold text-foreground truncate flex-1 text-sm">{project.title}</h2>
        <div className="flex items-center gap-2 shrink-0">
          {open.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
              {open.length} open
            </span>
          )}
          {done.length > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium">
              {done.length} done
            </span>
          )}
          <ChevronRight size={14} className="text-muted-foreground/40" />
        </div>
      </div>

      <div className="divide-y divide-border/50">
        {tasks.length === 0 ? (
          <p className="text-xs text-muted-foreground/60 px-4 py-4 text-center">No tasks yet</p>
        ) : (
          tasks.map((t, i) => <TaskRow key={t.id} task={t} index={i} />)
        )}
      </div>
    </div>
  );
}

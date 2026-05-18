import { FolderOpen } from "lucide-react";
import { useStore } from "../hooks/useStore";
import { TaskRow } from "./TaskRow";

export function TaskPane() {
  const projects = useStore((s) => s.projects);
  const tasks = useStore((s) => s.tasks);
  const selectedProjectId = useStore((s) => s.selectedProjectId);

  if (!selectedProjectId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center px-6">
          <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
            <FolderOpen size={20} className="text-primary" />
          </div>
          <p className="text-sm font-semibold text-foreground">Select a project</p>
          <p className="text-xs text-muted-foreground mt-1 max-w-xs">
            Or hold the mic and say <em>"add a task to…"</em> — Vox PM creates the project if needed.
          </p>
        </div>
      </div>
    );
  }

  const project = projects.find((p) => p.id === selectedProjectId);
  const title = project?.title ?? "Project";

  const visibleTasks = tasks
    .filter((t) => t.project_id === selectedProjectId)
    .sort((a, b) => a.position - b.position || a.created_at.localeCompare(b.created_at));

  const openCount = visibleTasks.filter((t) => t.status === "open").length;
  const doneCount = visibleTasks.filter((t) => t.status === "done").length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-5 border-b border-border flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <FolderOpen size={16} className="text-primary" />
        </div>
        <h1 className="font-semibold text-foreground text-base flex-1 truncate">{title}</h1>
        <div className="flex items-center gap-2 shrink-0">
          {openCount > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
              {openCount} open
            </span>
          )}
          {doneCount > 0 && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium">
              {doneCount} done
            </span>
          )}
        </div>
      </div>

      {/* Task list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {visibleTasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center px-6">
            <div className="mb-3 p-3 rounded-full bg-primary/10">
              <FolderOpen size={24} className="text-primary" />
            </div>
            <p className="text-sm font-semibold text-foreground">Voice is the fastest way in</p>
            <p className="text-xs text-muted-foreground mt-1 max-w-xs">
              Hold the mic and say <em>"add a task to {title}"</em> to get started.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {visibleTasks.map((t, i) => (
              <TaskRow key={t.id} task={t} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

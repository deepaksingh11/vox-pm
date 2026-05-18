import { Inbox } from "lucide-react";
import { useStore } from "../hooks/useStore";
import { ProjectCard } from "./ProjectCard";
import { TaskRow } from "./TaskRow";

export function ProjectList() {
  const projects = useStore((s) => s.projects);
  const tasks    = useStore((s) => s.tasks);
  const orphanTasks = tasks.filter((t) => !t.project_id);

  if (projects.length === 0 && orphanTasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-72 text-muted-foreground/40">
        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4">
          <Inbox size={28} className="opacity-50" />
        </div>
        <p className="text-sm font-medium text-muted-foreground">No projects yet</p>
        <p className="text-xs text-muted-foreground/60 mt-1">Start a session and speak to create tasks</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {projects.map((p) => (
        <ProjectCard
          key={p.id}
          project={p}
          tasks={tasks
            .filter((t) => t.project_id === p.id)
            .sort((a, b) => a.position - b.position)}
        />
      ))}

      {orphanTasks.length > 0 && (
        <div className="bg-card border border-border rounded-2xl overflow-hidden shadow-sm">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-muted/40">
            <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center shrink-0">
              <Inbox size={14} className="text-muted-foreground" />
            </div>
            <h2 className="font-semibold text-muted-foreground text-sm flex-1">Unassigned</h2>
            <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
              {orphanTasks.length}
            </span>
          </div>
          <div className="divide-y divide-border/50">
            {orphanTasks.map((t, i) => (
              <TaskRow key={t.id} task={t} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

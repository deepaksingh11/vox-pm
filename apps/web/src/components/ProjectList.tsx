import { Inbox } from "lucide-react";
import { useStore } from "../hooks/useStore";
import { ProjectCard } from "./ProjectCard";
import { TaskRow } from "./TaskRow";

export function ProjectList() {
  const projects = useStore((s) => s.projects);
  const tasks = useStore((s) => s.tasks);

  const orphanTasks = tasks.filter((t) => !t.project_id);

  if (projects.length === 0 && orphanTasks.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-600">
        <Inbox size={40} className="mb-3 opacity-30" />
        <p className="text-sm">No projects yet — start talking</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
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
        <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
          <div className="flex items-center gap-2.5 px-4 py-3 border-b border-slate-800">
            <Inbox size={16} className="text-slate-500 shrink-0" />
            <h2 className="font-semibold text-slate-400">Unassigned</h2>
            <span className="text-xs text-slate-500 ml-auto">{orphanTasks.length}</span>
          </div>
          <div className="py-1">
            {orphanTasks.map((t, i) => (
              <TaskRow key={t.id} task={t} index={i} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

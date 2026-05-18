import { FolderOpen } from "lucide-react";
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
    <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
      <div className="flex items-center gap-2.5 px-4 py-3 border-b border-slate-800">
        <FolderOpen size={16} className="text-brand-500 shrink-0" />
        <h2 className="font-semibold text-slate-100 truncate flex-1">{project.title}</h2>
        <span className="text-xs text-slate-500 shrink-0">
          {open.length} open{done.length > 0 ? ` · ${done.length} done` : ""}
        </span>
      </div>
      <div className="py-1">
        {tasks.length === 0 ? (
          <p className="text-xs text-slate-600 px-4 py-3">No tasks yet</p>
        ) : (
          tasks.map((t, i) => <TaskRow key={t.id} task={t} index={i} />)
        )}
      </div>
    </div>
  );
}

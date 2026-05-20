import { FolderOpen, Mic, Zap, Clock, Brain } from "lucide-react";
import { useStore } from "../hooks/useStore";
import { TaskRow } from "./TaskRow";

const VOICE_FACTS = [
  { icon: Zap, stat: "3×", label: "faster than typing", sub: "Stanford, 2016" },
  { icon: Clock, stat: "67 hrs", label: "saved per year", sub: "vs keyboard at 1k words/day" },
  { icon: Brain, stat: "20%", label: "fewer errors", sub: "voice vs typed input" },
];

export function TaskPane() {
  const projects = useStore((s) => s.projects);
  const tasks = useStore((s) => s.tasks);
  const selectedProjectId = useStore((s) => s.selectedProjectId);
  const agentThinking = useStore((s) => s.agentThinking);

  if (!selectedProjectId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center px-6 max-w-lg w-full">
          {/* Icon */}
          <div className="mx-auto mb-5 w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Mic size={26} className="text-primary" />
          </div>

          <h2 className="text-base font-semibold text-foreground mb-1">Voice beats the keyboard</h2>
          <p className="text-xs text-muted-foreground mb-8 max-w-xs mx-auto">
            Say <em className="text-foreground/80 not-italic font-medium">"add a task to…"</em> — Vox PM picks the project or creates one on the fly.
          </p>

          {/* Stat cards */}
          <div className="grid grid-cols-3 gap-3 mb-8">
            {VOICE_FACTS.map(({ icon: Icon, stat, label, sub }) => (
              <div
                key={stat}
                className="rounded-xl border border-border/60 bg-card/60 px-3 py-3.5 flex flex-col items-center gap-1 hover:border-primary/30 hover:bg-primary/5 transition-colors"
              >
                <Icon size={14} className="text-primary/70 mb-0.5" />
                <span className="text-lg font-bold text-foreground leading-none">{stat}</span>
                <span className="text-[10px] font-medium text-foreground/70 text-center leading-tight">{label}</span>
                <span className="text-[9px] text-muted-foreground/50 text-center leading-tight">{sub}</span>
              </div>
            ))}
          </div>

          {/* CTA hint */}
          <div className="inline-flex items-center gap-2 px-3.5 py-2 rounded-full bg-primary/8 border border-primary/15 text-xs text-muted-foreground">
            <Mic size={11} className="text-primary" />
            Hold mic · Speak · Done
          </div>
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
      <div className={`flex-1 overflow-y-auto scrollbar-thin transition-opacity duration-200 ${agentThinking ? "opacity-50 pointer-events-none" : ""}`}>
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

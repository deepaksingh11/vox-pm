import { create } from "zustand";
import type { ActionEntry, Project, Task, WSEvent } from "../lib/types";
import { api } from "../lib/api";

interface Store {
  projects: Project[];
  tasks: Task[];
  actions: ActionEntry[];
  debugEvents: WSEvent[];
  partialTranscript: string;
  finalTranscript: string;
  agentThinking: boolean;
  clarification: { question: string; candidates: string[] } | null;
  selectedProjectId: string | null;

  loadInitialState: () => Promise<void>;
  applyEvent: (event: WSEvent) => void;
  clearClarification: () => void;
  clearAgentState: () => void;
  setSelectedProject: (id: string | null) => void;
  toggleTaskDone: (taskId: string) => void;
  deleteTask: (taskId: string) => void;
  deleteProject: (projectId: string) => void;
  renameProject: (projectId: string, title: string) => void;
  createProject: (title: string) => Promise<void>;
}

// agentThinking is set on transcript.final but only cleared by tool/entity events.
// If the agent responds with speech only (no tool call), nothing clears it — UI freezes.
// This timer auto-clears the flag after 12 s as a fallback.
let _thinkingTimer: ReturnType<typeof setTimeout> | null = null;

function _clearThinkingTimer() {
  if (_thinkingTimer) { clearTimeout(_thinkingTimer); _thinkingTimer = null; }
}

function summarize(event: WSEvent): string {
  const d = event.data;
  switch (event.type) {
    case "tool.started":
      return `Calling ${d.name as string}…`;
    case "tool.completed":
      return `Done ${d.name as string} (${d.duration_ms as number}ms)`;
    case "tool.failed":
      return `Failed ${d.name as string}: ${d.error as string}`;
    case "project.created":
      return `Created project "${(d.project as Project)?.title}"`;
    case "project.updated":
      return `Updated project "${(d.project as Project)?.title}"`;
    case "project.deleted":
      return `Deleted project`;
    case "task.created":
      return `Added task "${(d.task as Task)?.title}"`;
    case "task.updated": {
      const fields = (d.changed_fields as string[])?.join(", ") ?? "";
      return `Updated task "${(d.task as Task)?.title}"${fields ? ` (${fields})` : ""}`;
    }
    case "task.deleted":
      return `Deleted task`;
    case "task.moved":
      return `Moved task "${(d.task as Task)?.title}"`;
    case "clarification.ask":
      return `Asked: ${d.question as string}`;
    default:
      return event.type;
  }
}

export const useStore = create<Store>((set, get) => ({
  projects: [],
  tasks: [],
  actions: [],
  debugEvents: [],
  partialTranscript: "",
  finalTranscript: "",
  agentThinking: false,
  clarification: null,
  selectedProjectId: null,

  loadInitialState: async () => {
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const [serverProjects, serverTasks] = await Promise.all([
          api.projects.list(),
          api.tasks.list(),
        ]);
        // Merge by id rather than overwrite — a live task.created event that lands
        // before this response would otherwise be wiped by set({tasks}).
        set((s) => {
          const serverProjectIds = new Set(serverProjects.map((p) => p.id));
          const serverTaskIds = new Set(serverTasks.map((t) => t.id));
          return {
            projects: [
              ...serverProjects,
              ...s.projects.filter((p) => !serverProjectIds.has(p.id)),
            ],
            tasks: [
              ...serverTasks,
              ...s.tasks.filter((t) => !serverTaskIds.has(t.id)),
            ],
          };
        });
        return;
      } catch {
        if (attempt < 4) await new Promise((r) => setTimeout(r, 300 * (attempt + 1)));
      }
    }
  },

  setSelectedProject: (id) => set({ selectedProjectId: id }),

  toggleTaskDone: (taskId) => {
    const { tasks } = get();
    const task = tasks.find((t) => t.id === taskId);
    if (!task) return;
    const newStatus = task.status === "done" ? "open" : "done";
    const prevTasks = tasks;
    set({ tasks: tasks.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)) });
    void api.tasks.update(taskId, { status: newStatus }).catch(() => {
      set({ tasks: prevTasks });
    });
  },

  deleteTask: (taskId) => {
    const prevTasks = get().tasks;
    set({ tasks: prevTasks.filter((t) => t.id !== taskId) });
    void api.tasks.delete(taskId).catch(() => {
      set({ tasks: prevTasks });
    });
  },

  deleteProject: (projectId) => {
    const { selectedProjectId, projects, tasks } = get();
    const prevProjects = projects;
    const prevTasks = tasks;
    const prevSelected = selectedProjectId;
    set({
      projects: projects.filter((p) => p.id !== projectId),
      tasks: tasks.map((t) =>
        t.project_id === projectId ? { ...t, project_id: null } : t
      ),
      selectedProjectId: selectedProjectId === projectId ? null : selectedProjectId,
    });
    void api.projects.delete(projectId).catch(() => {
      set({ projects: prevProjects, tasks: prevTasks, selectedProjectId: prevSelected });
    });
  },

  renameProject: (projectId, title) => {
    const prevProjects = get().projects;
    set({ projects: prevProjects.map((p) => p.id === projectId ? { ...p, title } : p) });
    void api.projects.update(projectId, { title }).catch(() => {
      set({ projects: prevProjects });
    });
  },

  createProject: async (title) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    const project = await api.projects.create(trimmed);
    set((s) => s.projects.find((p) => p.id === project.id)
      ? s
      : { projects: [...s.projects, project], selectedProjectId: project.id });
  },

  applyEvent: (event) => {
    if (event.type === "ping") return;

    // Functional updaters ensure each set() reads live state rather than a snapshot
    // captured once at the top — prevents burst events from clobbering each other.
    set((s) => ({ debugEvents: [...s.debugEvents, event].slice(-100) }));

    switch (event.type) {
      case "transcript.partial":
        set({ partialTranscript: event.data.text as string });
        break;

      case "transcript.final":
        _clearThinkingTimer();
        _thinkingTimer = setTimeout(() => { set({ agentThinking: false }); _thinkingTimer = null; }, 12_000);
        set({
          finalTranscript: event.data.text as string,
          partialTranscript: "",
          agentThinking: true,
        });
        break;

      case "agent.thinking":
        set({ agentThinking: true });
        break;

      case "agent.error":
        _clearThinkingTimer();
        set({ agentThinking: false });
        break;

      case "tool.started":
        set((s) => ({ actions: addAction(s.actions, event), clarification: null }));
        break;

      case "tool.completed":
        _clearThinkingTimer();
        set((s) => ({ agentThinking: false, actions: addAction(s.actions, event) }));
        break;

      case "tool.failed":
        _clearThinkingTimer();
        set((s) => ({ agentThinking: false, actions: addAction(s.actions, event) }));
        break;

      case "project.created": {
        _clearThinkingTimer();
        const p = event.data.project as Project;
        set((s) => ({
          projects: s.projects.find((x) => x.id === p.id)
            ? s.projects.map((x) => (x.id === p.id ? p : x))
            : [...s.projects, p],
          agentThinking: false,
          actions: addAction(s.actions, event),
        }));
        break;
      }

      case "project.updated": {
        _clearThinkingTimer();
        const p = event.data.project as Project;
        set((s) => ({
          projects: s.projects.map((x) => (x.id === p.id ? p : x)),
          agentThinking: false,
          actions: addAction(s.actions, event),
        }));
        break;
      }

      case "project.deleted": {
        _clearThinkingTimer();
        const id = event.data.id as string;
        set((s) => ({
          projects: s.projects.filter((x) => x.id !== id),
          tasks: s.tasks.map((t) =>
            t.project_id === id ? { ...t, project_id: null } : t
          ),
          selectedProjectId: s.selectedProjectId === id ? null : s.selectedProjectId,
          agentThinking: false,
          actions: addAction(s.actions, event),
        }));
        break;
      }

      case "task.created": {
        _clearThinkingTimer();
        const t = event.data.task as Task;
        set((s) => {
          const already = s.tasks.find((x) => x.id === t.id);
          return {
            tasks: already ? s.tasks.map((x) => (x.id === t.id ? t : x)) : [...s.tasks, t],
            agentThinking: false,
            actions: addAction(s.actions, event),
          };
        });
        break;
      }

      case "task.updated": {
        _clearThinkingTimer();
        const t = event.data.task as Task;
        set((s) => ({
          tasks: s.tasks.map((x) => (x.id === t.id ? t : x)),
          agentThinking: false,
          actions: addAction(s.actions, event),
        }));
        break;
      }

      case "task.deleted": {
        _clearThinkingTimer();
        const id = event.data.id as string;
        set((s) => ({
          tasks: s.tasks.filter((x) => x.id !== id),
          agentThinking: false,
          actions: addAction(s.actions, event),
        }));
        break;
      }

      case "task.moved": {
        _clearThinkingTimer();
        const t = event.data.task as Task;
        const fromId = event.data.from_project_id as string | null;
        const toId = event.data.to_project_id as string | null;
        set((s) => {
          const fromTitle = s.projects.find((p) => p.id === fromId)?.title ?? "Unassigned";
          const toTitle = s.projects.find((p) => p.id === toId)?.title ?? "Unassigned";
          const movedSummary = `Moved "${t.title}" from ${fromTitle} → ${toTitle}`;
          return {
            tasks: s.tasks.map((x) => (x.id === t.id ? t : x)),
            agentThinking: false,
            actions: addAction(s.actions, event, movedSummary),
          };
        });
        break;
      }

      case "clarification.ask":
        _clearThinkingTimer();
        set({
          clarification: {
            question: event.data.question as string,
            candidates: (event.data.candidates as string[]) ?? [],
          },
          agentThinking: false,
        });
        break;

      case "clarification.resolved":
        set({ clarification: null });
        break;
    }
  },

  clearClarification: () => set({ clarification: null }),
  clearAgentState: () => {
    _clearThinkingTimer();
    set({ agentThinking: false, clarification: null, partialTranscript: "", finalTranscript: "" });
  },
}));

function addAction(actions: ActionEntry[], event: WSEvent, summaryOverride?: string): ActionEntry[] {
  const entry: ActionEntry = {
    id: crypto.randomUUID(),
    type: event.type as ActionEntry["type"],
    ts: event.ts,
    summary: summaryOverride ?? summarize(event),
  };
  return [entry, ...actions].slice(0, 50);
}

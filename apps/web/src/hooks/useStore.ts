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
  setSelectedProject: (id: string | null) => void;
  toggleTaskDone: (taskId: string) => void;
  deleteTask: (taskId: string) => void;
  deleteProject: (projectId: string) => void;
  renameProject: (projectId: string, title: string) => void;
  createProject: (title: string) => Promise<void>;
}

let _actionCounter = 0;

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
        const [projects, tasks] = await Promise.all([api.projects.list(), api.tasks.list()]);
        set({ projects, tasks });
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
    set({ tasks: tasks.map((t) => (t.id === taskId ? { ...t, status: newStatus } : t)) });
    void api.tasks.update(taskId, { status: newStatus });
  },

  deleteTask: (taskId) => {
    set({ tasks: get().tasks.filter((t) => t.id !== taskId) });
    void api.tasks.delete(taskId);
  },

  deleteProject: (projectId) => {
    const { selectedProjectId } = get();
    set({
      projects: get().projects.filter((p) => p.id !== projectId),
      tasks: get().tasks.map((t) =>
        t.project_id === projectId ? { ...t, project_id: null } : t
      ),
      selectedProjectId: selectedProjectId === projectId ? null : selectedProjectId,
    });
    void api.projects.delete(projectId);
  },

  renameProject: (projectId, title) => {
    void api.projects.update(projectId, { title });
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

    const state = get();
    set({ debugEvents: [...state.debugEvents, event].slice(-100) });

    switch (event.type) {
      case "transcript.partial":
        set({ partialTranscript: event.data.text as string });
        break;

      case "transcript.final":
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
        set({ agentThinking: false });
        break;

      case "tool.started":
        set({ actions: addAction(state.actions, event), clarification: null });
        break;

      case "tool.completed":
        set({ actions: addAction(state.actions, event) });
        break;

      case "tool.failed":
        set({ agentThinking: false, actions: addAction(state.actions, event) });
        break;

      case "project.created": {
        const p = event.data.project as Project;
        const already = state.projects.find((x) => x.id === p.id);
        set({
          projects: already ? state.projects.map((x) => (x.id === p.id ? p : x)) : [...state.projects, p],
          agentThinking: false,
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "project.updated": {
        const p = event.data.project as Project;
        set({
          projects: state.projects.map((x) => (x.id === p.id ? p : x)),
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "project.deleted": {
        const id = event.data.id as string;
        set({
          projects: state.projects.filter((x) => x.id !== id),
          tasks: state.tasks.map((t) =>
            t.project_id === id ? { ...t, project_id: null } : t
          ),
          selectedProjectId: state.selectedProjectId === id ? null : state.selectedProjectId,
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "task.created": {
        const t = event.data.task as Task;
        const already = state.tasks.find((x) => x.id === t.id);
        set({
          tasks: already ? state.tasks.map((x) => (x.id === t.id ? t : x)) : [...state.tasks, t],
          agentThinking: false,
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "task.updated": {
        const t = event.data.task as Task;
        set({
          tasks: state.tasks.map((x) => (x.id === t.id ? t : x)),
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "task.deleted": {
        const id = event.data.id as string;
        set({
          tasks: state.tasks.filter((x) => x.id !== id),
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "task.moved": {
        const t = event.data.task as Task;
        set({
          tasks: state.tasks.map((x) => (x.id === t.id ? t : x)),
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "clarification.ask":
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
}));

function addAction(actions: ActionEntry[], event: WSEvent): ActionEntry[] {
  const entry: ActionEntry = {
    id: String(++_actionCounter),
    type: event.type as ActionEntry["type"],
    ts: event.ts,
    summary: summarize(event),
  };
  return [entry, ...actions].slice(0, 50);
}

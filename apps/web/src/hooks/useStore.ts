import { create } from "zustand";
import type { ActionEntry, Project, Task, WSEvent } from "../lib/types";
import { api } from "../lib/api";

interface Store {
  projects: Project[];
  tasks: Task[];
  actions: ActionEntry[];
  partialTranscript: string;
  finalTranscript: string;
  agentThinking: boolean;
  clarification: { question: string; candidates: string[] } | null;

  loadInitialState: () => Promise<void>;
  applyEvent: (event: WSEvent) => void;
  clearClarification: () => void;
}

let _actionCounter = 0;

function summarize(event: WSEvent): string {
  const d = event.data;
  switch (event.type) {
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
  partialTranscript: "",
  finalTranscript: "",
  agentThinking: false,
  clarification: null,

  loadInitialState: async () => {
    const [projects, tasks] = await Promise.all([api.projects.list(), api.tasks.list()]);
    set({ projects, tasks });
  },

  applyEvent: (event) => {
    if (event.type === "ping") return;
    const state = get();

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

      case "project.created": {
        const p = event.data.project as Project;
        set({
          projects: [...state.projects, p],
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
          actions: addAction(state.actions, event),
        });
        break;
      }

      case "task.created": {
        const t = event.data.task as Task;
        set({
          tasks: [...state.tasks, t],
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

import type { Project, Task } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const r = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!r.ok && r.status !== 404) throw new Error(`${r.status} ${r.statusText}`);
}

export const api = {
  projects: {
    list: () => get<Project[]>("/api/projects"),
  },
  tasks: {
    list: (projectId?: string) =>
      get<Task[]>(`/api/tasks${projectId ? `?project_id=${projectId}` : ""}`),
  },
  voice: {
    createSession: () =>
      post<{ session_id: string; room_url: string; token: string }>("/api/voice/session"),
    endSession: (sessionId: string) => del(`/api/voice/session/${sessionId}`),
  },
};

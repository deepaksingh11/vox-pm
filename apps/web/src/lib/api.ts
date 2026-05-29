import type { Project, Task } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";

// Stable per-browser identity — read once from localStorage so REST, voice,
// and WebSocket all publish/subscribe on the same channel.
const _CLIENT_ID_KEY = "vox-pm-client-id";
function _initClientId(): string {
  const stored = localStorage.getItem(_CLIENT_ID_KEY);
  if (stored) return stored;
  const id = crypto.randomUUID();
  localStorage.setItem(_CLIENT_ID_KEY, id);
  return id;
}
/** Persistent client identifier. Import this wherever the id is needed. */
export const clientId: string = _initClientId();

const _clientHeaders = { "X-Client-Id": clientId };

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { headers: _clientHeaders });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body
      ? { "Content-Type": "application/json", ..._clientHeaders }
      : { ..._clientHeaders },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ..._clientHeaders },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const r = await fetch(`${BASE}${path}`, { method: "DELETE", headers: _clientHeaders });
  if (!r.ok && r.status !== 404) throw new Error(`${r.status} ${r.statusText}`);
}

export const api = {
  projects: {
    list: () => get<Project[]>("/api/projects"),
    create: (title: string) => post<Project>("/api/projects", { title }),
    update: (id: string, body: { title?: string }) =>
      patch<Project>(`/api/projects/${id}`, body),
    delete: (id: string) => del(`/api/projects/${id}`),
  },
  tasks: {
    list: (projectId?: string) =>
      get<Task[]>(`/api/tasks${projectId ? `?project_id=${projectId}` : ""}`),
    update: (id: string, body: Partial<Pick<Task, "status" | "urgent" | "title">>) =>
      patch<Task>(`/api/tasks/${id}`, body),
    delete: (id: string) => del(`/api/tasks/${id}`),
  },
  voice: {
    // Send clientId in body so the server uses it as the pipeline event channel.
    createSession: () =>
      post<{ session_id: string; room_url: string; token: string }>(
        "/api/voice/session",
        { client_id: clientId },
      ),
    endSession: (sessionId: string) => del(`/api/voice/session/${sessionId}`),
  },
};

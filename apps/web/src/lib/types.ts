export interface Project {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  project_id: string | null;
  title: string;
  description: string | null;
  urgent: boolean;
  due_at: string | null;
  reminder_at: string | null;
  status: "open" | "in_progress" | "blocked" | "cancelled" | "done";
  position: number;
  created_at: string;
  updated_at: string;
}

export type EventType =
  | "transcript.partial"
  | "transcript.final"
  | "agent.thinking"
  | "agent.error"
  | "tool.started"
  | "tool.completed"
  | "tool.failed"
  | "project.created"
  | "project.updated"
  | "project.deleted"
  | "task.created"
  | "task.updated"
  | "task.deleted"
  | "task.moved"
  | "reminder.fired"
  | "clarification.ask"
  | "clarification.resolved";

export interface WSEvent {
  type: EventType | "ping";
  ts: string;
  data: Record<string, unknown>;
}

export interface ActionEntry {
  id: string;
  type: EventType;
  ts: string;
  summary: string;
}

export type VoiceSessionStatus =
  | "idle"
  | "connecting"
  | "active"
  | "error"
  | "disconnecting";

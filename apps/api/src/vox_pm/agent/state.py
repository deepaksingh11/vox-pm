"""Per-session mutable context for reference resolution."""

from dataclasses import dataclass, field
from typing import Literal


EntityKind = Literal["project", "task"]


@dataclass
class EntityRef:
    id: str
    title: str
    kind: EntityKind
    project_id: str | None = None  # for tasks


@dataclass
class SessionState:
    session_id: str
    # rolling window of recently touched entities (newest last)
    recent: list[EntityRef] = field(default_factory=list)
    # last explicitly focused project (e.g. "under it add three tasks")
    current_project_id: str | None = None

    _max_recent: int = 20

    def touch(self, ref: EntityRef) -> None:
        self.recent = [r for r in self.recent if r.id != ref.id]
        self.recent.append(ref)
        if len(self.recent) > self._max_recent:
            self.recent = self.recent[-self._max_recent:]
        if ref.kind == "project":
            self.current_project_id = ref.id
        elif ref.project_id:
            self.current_project_id = ref.project_id

    def last_of_kind(self, kind: EntityKind) -> EntityRef | None:
        for r in reversed(self.recent):
            if r.kind == kind:
                return r
        return None

    def snapshot_text(self, projects: list, tasks: list) -> str:
        """Compact text summary injected into LLM context each turn."""
        lines = ["## Current workspace state"]
        if not projects:
            lines.append("(empty — no projects yet)")
        for p in projects:
            lines.append(f"PROJECT id={p['id']} title={p['title']!r}")
            project_tasks = [t for t in tasks if t.get("project_id") == p["id"]]
            for i, t in enumerate(project_tasks):
                urgency = " [URGENT]" if t.get("urgent") else ""
                due = f" due={t['due_at']}" if t.get("due_at") else ""
                lines.append(f"  TASK[{i}] id={t['id']} title={t['title']!r}{urgency}{due}")
        orphans = [t for t in tasks if not t.get("project_id")]
        if orphans:
            lines.append("UNASSIGNED TASKS:")
            for i, t in enumerate(orphans):
                urgency = " [URGENT]" if t.get("urgent") else ""
                lines.append(f"  TASK[{i}] id={t['id']} title={t['title']!r}{urgency}")
        if self.recent:
            last = self.recent[-1]
            lines.append(f"## Last touched: {last.kind} id={last.id} title={last.title!r}")
        return "\n".join(lines)


# in-memory store keyed by session_id
_states: dict[str, SessionState] = {}


def get_state(session_id: str) -> SessionState:
    if session_id not in _states:
        _states[session_id] = SessionState(session_id=session_id)
    return _states[session_id]


def clear_state(session_id: str) -> None:
    _states.pop(session_id, None)

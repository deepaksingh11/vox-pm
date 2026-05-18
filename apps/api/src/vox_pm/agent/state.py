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
    recent: list[EntityRef] = field(default_factory=list)
    current_project_id: str | None = None
    # short alias → full UUID (e.g. "P1" → "550e8400-...")
    _alias_map: dict[str, str] = field(default_factory=dict)

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

    def resolve_id(self, alias_or_id: str) -> str:
        """Return full UUID for an alias like 'P1'/'T3', or pass-through if already full."""
        return self._alias_map.get(alias_or_id, alias_or_id)

    def last_of_kind(self, kind: EntityKind) -> EntityRef | None:
        for r in reversed(self.recent):
            if r.kind == kind:
                return r
        return None

    def snapshot_text(self, projects: list, tasks: list) -> str:
        """Compact workspace summary injected into LLM context each turn."""
        self._alias_map.clear()
        lines: list[str] = []

        if not projects and not tasks:
            lines.append("WS: empty")
        else:
            lines.append("WS:")
            p_counter = 0
            t_counter = 0
            for p in projects:
                p_counter += 1
                alias = f"P{p_counter}"
                self._alias_map[alias] = p["id"]
                project_tasks = [t for t in tasks if t.get("project_id") == p["id"]]
                lines.append(f'{alias} "{p["title"]}"')
                for t in project_tasks:
                    t_counter += 1
                    talias = f"T{t_counter}"
                    self._alias_map[talias] = t["id"]
                    flags = ""
                    if t.get("urgent"):
                        flags += "!"
                    if t.get("due_at"):
                        flags += f" due={t['due_at']}"
                    lines.append(f'  {talias} "{t["title"]}"{flags}')
            orphans = [t for t in tasks if not t.get("project_id")]
            if orphans:
                lines.append("UNASSIGNED:")
                for t in orphans:
                    t_counter += 1
                    talias = f"T{t_counter}"
                    self._alias_map[talias] = t["id"]
                    flags = "!" if t.get("urgent") else ""
                    lines.append(f'  {talias} "{t["title"]}"{flags}')

        if self.recent:
            last = self.recent[-1]
            # find alias for last touched
            rev = {v: k for k, v in self._alias_map.items()}
            alias = rev.get(last.id, last.id[:8])
            lines.append(f'^{last.kind[0].upper()} {alias} "{last.title}"')

        return "\n".join(lines)


_states: dict[str, SessionState] = {}


def get_state(session_id: str) -> SessionState:
    if session_id not in _states:
        _states[session_id] = SessionState(session_id=session_id)
    return _states[session_id]


def clear_state(session_id: str) -> None:
    _states.pop(session_id, None)

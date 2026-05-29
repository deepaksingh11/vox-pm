"""Per-session mutable context for reference resolution."""

import re
from dataclasses import dataclass, field
from typing import Literal


EntityKind = Literal["project", "task"]

_ALIAS_RE = re.compile(r"^[PT]\d+$")


@dataclass
class EntityRef:
    id: str
    title: str
    kind: EntityKind
    project_id: str | None = None


@dataclass
class SessionState:
    session_id: str
    recent: list[EntityRef] = field(default_factory=list)
    current_project_id: str | None = None

    # Never cleared — aliases are permanent for the session lifetime.
    # Renumbering aliases across turns causes the LLM to delete the wrong entity.
    _alias_map: dict[str, str] = field(default_factory=dict)
    _id_to_alias: dict[str, str] = field(default_factory=dict)
    _p_counter: int = 0
    _t_counter: int = 0
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

    def resolve_id(self, alias_or_id: str) -> str | None:
        """Resolve alias → UUID, pass through full UUIDs, return None for unknown aliases.

        None signals an unknown reference (alias-shaped but not in map) so callers
        can return an error rather than passing a bogus string to the DB.
        """
        if alias_or_id in self._alias_map:
            return self._alias_map[alias_or_id]
        if _ALIAS_RE.match(alias_or_id):
            return None
        return alias_or_id

    def last_of_kind(self, kind: EntityKind) -> EntityRef | None:
        for r in reversed(self.recent):
            if r.kind == kind:
                return r
        return None

    def _get_or_create_alias(self, entity_id: str, kind: EntityKind) -> str:
        if entity_id in self._id_to_alias:
            return self._id_to_alias[entity_id]
        if kind == "project":
            self._p_counter += 1
            alias = f"P{self._p_counter}"
        else:
            self._t_counter += 1
            alias = f"T{self._t_counter}"
        self._alias_map[alias] = entity_id
        self._id_to_alias[entity_id] = alias
        return alias

    def snapshot_text(self, projects: list, tasks: list) -> str:
        lines: list[str] = []

        if not projects and not tasks:
            lines.append("WS: empty")
        else:
            lines.append("WS:")
            for p in projects:
                alias = self._get_or_create_alias(p["id"], "project")
                project_tasks = [t for t in tasks if t.get("project_id") == p["id"]]
                lines.append(f'{alias} "{p["title"]}"')
                for t in project_tasks:
                    talias = self._get_or_create_alias(t["id"], "task")
                    flags = ""
                    if t.get("urgent"):
                        flags += "!"
                    if t.get("due_at"):
                        flags += f" due={t['due_at']}"
                    lines.append(f'  {talias} "{t["title"]}"{flags}')

        if self.recent:
            last = self.recent[-1]
            alias = self._id_to_alias.get(last.id, last.id[:8])
            lines.append(f'^{last.kind[0].upper()} {alias} "{last.title}"')

        return "\n".join(lines)


_states: dict[str, SessionState] = {}


def get_state(session_id: str) -> SessionState:
    if session_id not in _states:
        _states[session_id] = SessionState(session_id=session_id)
    return _states[session_id]


def clear_state(session_id: str) -> None:
    _states.pop(session_id, None)

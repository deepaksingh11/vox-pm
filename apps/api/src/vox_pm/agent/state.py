"""Per-session mutable context for reference resolution."""

import re
import time
from dataclasses import dataclass, field
from typing import Literal

EntityKind = Literal["project", "task"]

_ALIAS_RE = re.compile(r"^[PT]\d+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

# Window within which an identical create_task (same title+project) is treated as a
# retry and deduped. Short enough not to block a user genuinely making two same-named
# tasks minutes apart; long enough to absorb an interruption/network-blip retry.
_CREATE_DEDUPE_TTL_SECONDS = 8.0


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

    # (title, project_id) -> (task_id, monotonic_ts) for short-window create dedupe.
    _recent_creates: dict[tuple[str, str | None], tuple[str, float]] = field(default_factory=dict)

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
        """Resolve alias → UUID, pass through real UUIDs, return None for anything else.

        None signals an unknown reference so callers return an error rather than
        passing a bogus value to the DB. Critically, a free-text string (e.g. the LLM
        passing a project *title* as project_id) is NOT a valid reference — letting it
        through caused a FK violation. Only known aliases (P1/T3) and real UUIDs (e.g.
        an id echoed back from a prior tool result) resolve.
        """
        if alias_or_id in self._alias_map:
            return self._alias_map[alias_or_id]
        if _UUID_RE.match(alias_or_id):
            return alias_or_id
        return None

    def check_recent_create(self, title: str, project_id: str | None) -> str | None:
        """Return the id of a task created with the same title+project within the
        dedupe window, else None. Used to make create_task idempotent under retries."""
        entry = self._recent_creates.get((title, project_id))
        if entry is None:
            return None
        task_id, ts = entry
        if time.monotonic() - ts > _CREATE_DEDUPE_TTL_SECONDS:
            del self._recent_creates[(title, project_id)]
            return None
        return task_id

    def record_create(self, title: str, project_id: str | None, task_id: str) -> None:
        self._recent_creates[(title, project_id)] = (task_id, time.monotonic())

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

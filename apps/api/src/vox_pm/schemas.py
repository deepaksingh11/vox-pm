from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["open", "in_progress", "blocked", "cancelled", "done"]

# Bounds shared by REST DTOs and LLM tool args: a title is a spoken phrase, not a
# document — cap it before it reaches Postgres.
TITLE_MAX = 200
DESCRIPTION_MAX = 2000

# --- REST response shapes ---

class ProjectRead(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskRead(BaseModel):
    id: str
    project_id: str | None
    title: str
    description: str | None
    urgent: bool
    due_at: datetime | None
    reminder_at: datetime | None
    reminder_fired: bool
    status: TaskStatus
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    project_id: str | None = None
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    urgent: bool = False
    due_at: datetime | None = None
    reminder_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX)
    project_id: str | None = None
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    urgent: bool | None = None
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    status: TaskStatus | None = None


# --- WS event shapes ---

EventType = Literal[
    "transcript.partial",
    "transcript.final",
    "agent.thinking",
    "agent.error",
    "tool.started",
    "tool.completed",
    "tool.failed",
    "project.created",
    "project.updated",
    "project.deleted",
    "task.created",
    "task.updated",
    "task.deleted",
    "task.moved",
    "reminder.fired",
    "clarification.ask",
    "clarification.resolved",
]


class WSEvent(BaseModel):
    type: EventType
    ts: datetime
    data: dict[str, Any] = {}


# --- Voice session ---

class SessionCreateRequest(BaseModel):
    # The client sends its stable localStorage UUID so REST, voice, and WS all use the same channel.
    client_id: str


class SessionCreateResponse(BaseModel):
    session_id: str
    room_url: str
    token: str

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    from datetime import UTC
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str | None = Field(default=None, foreign_key="projects.id", index=True)
    title: str
    description: str | None = None
    urgent: bool = False
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    status: str = "open"  # "open" | "done"
    position: int = Field(default=0)  # for "first task" / "last task" resolution
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

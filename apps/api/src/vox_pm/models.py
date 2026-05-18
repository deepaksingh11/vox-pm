import uuid
from datetime import datetime

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    from datetime import UTC
    return datetime.now(UTC).replace(tzinfo=None)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("title", name="uq_projects_title"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"
    __table_args__ = (
        # Covers: WHERE project_id = X ORDER BY position, created_at
        Index("ix_tasks_project_position", "project_id", "position", "created_at"),
    )

    id: str = Field(default_factory=_uuid, primary_key=True)
    project_id: str | None = Field(default=None, foreign_key="projects.id")
    title: str
    description: str | None = None
    urgent: bool = False
    due_at: datetime | None = None
    reminder_at: datetime | None = None
    status: str = "open"
    position: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

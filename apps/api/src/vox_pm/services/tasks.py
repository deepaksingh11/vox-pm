from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from vox_pm.events.bus import publish
from vox_pm.models import Project, Task
from vox_pm.schemas import ProjectRead, TaskRead

UPDATABLE_TASK_FIELDS = {"title", "description", "urgent", "due_at", "reminder_at", "status"}
VALID_TASK_STATUSES = {"open", "in_progress", "blocked", "cancelled", "done"}


async def list_tasks(
    session: AsyncSession, project_id: str | None = None
) -> list[TaskRead]:
    query = select(Task).order_by(Task.position, Task.created_at)
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    result = await session.exec(query)
    return [TaskRead.model_validate(t) for t in result.all()]


async def get_task(session: AsyncSession, task_id: str) -> Task | None:
    return await session.get(Task, task_id)


async def _next_position(session: AsyncSession, project_id: str | None) -> int:
    stmt = select(func.coalesce(func.max(Task.position), 0))
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    else:
        stmt = stmt.where(Task.project_id.is_(None))
    result = await session.exec(stmt)
    return (result.first() or 0) + 1


async def create_task(
    session: AsyncSession,
    title: str,
    project_id: str | None = None,
    description: str | None = None,
    urgent: bool = False,
    due_at: datetime | None = None,
    reminder_at: datetime | None = None,
    session_id: str = "default",
) -> TaskRead:
    # Retry on position collision (uq_tasks_project_position)
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            position = await _next_position(session, project_id)
            task = Task(
                title=title,
                project_id=project_id,
                description=description,
                urgent=urgent,
                due_at=due_at,
                reminder_at=reminder_at,
                position=position,
            )
            session.add(task)
            await session.commit()
            break
        except IntegrityError as exc:
            last_exc = exc
            await session.rollback()
            if attempt == 2:
                raise
    else:
        raise last_exc  # type: ignore[misc]

    await session.refresh(task)
    read = TaskRead.model_validate(task)
    await publish(session_id, "task.created", {"task": read.model_dump(mode="json")})
    return read


async def update_task(
    session: AsyncSession,
    task_id: str,
    session_id: str = "default",
    **kwargs,
) -> TaskRead | None:
    task = await session.get(Task, task_id)
    if not task:
        return None

    changed = []
    for field_name, value in kwargs.items():
        if field_name not in UPDATABLE_TASK_FIELDS:
            continue
        if field_name == "status" and value is not None and value not in VALID_TASK_STATUSES:
            continue
        # Allow None to clear nullable fields (due_at, reminder_at, description).
        # The previous `if value is not None` guard made clearing these impossible.
        setattr(task, field_name, value)
        changed.append(field_name)

    task.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    read = TaskRead.model_validate(task)
    await publish(
        session_id,
        "task.updated",
        {"task": read.model_dump(mode="json"), "changed_fields": changed},
    )
    return read


async def move_task(
    session: AsyncSession,
    task_id: str,
    project_id: str | None,
    session_id: str = "default",
) -> TaskRead | None:
    task = await session.get(Task, task_id)
    if not task:
        return None
    from_project_id = task.project_id

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            task.project_id = project_id
            task.position = await _next_position(session, project_id)
            task.updated_at = datetime.now(UTC).replace(tzinfo=None)
            session.add(task)
            await session.commit()
            break
        except IntegrityError as exc:
            last_exc = exc
            await session.rollback()
            task = await session.get(Task, task_id)
            if not task:
                return None
            if attempt == 2:
                raise
    else:
        raise last_exc  # type: ignore[misc]

    await session.refresh(task)
    read = TaskRead.model_validate(task)
    await publish(
        session_id,
        "task.moved",
        {
            "id": task_id,
            "task": read.model_dump(mode="json"),
            "from_project_id": from_project_id,
            "to_project_id": project_id,
        },
    )
    return read


async def delete_task(
    session: AsyncSession,
    task_id: str,
    session_id: str = "default",
) -> bool:
    task = await session.get(Task, task_id)
    if not task:
        return False
    await session.delete(task)
    await session.commit()
    await publish(session_id, "task.deleted", {"id": task_id})
    return True


async def convert_task_to_project(
    session: AsyncSession,
    task_id: str,
    session_id: str = "default",
) -> ProjectRead | None:
    """Create project then delete task in a single commit.

    Create-first ordering: a failure before commit leaves the task intact.
    Old code committed the delete first, then created the project — task was
    permanently gone if create raised.
    """
    task = await session.get(Task, task_id)
    if not task:
        return None
    title = task.title

    project = Project(title=title)
    session.add(project)
    await session.flush()  # get id; raises IntegrityError on duplicate title

    await session.delete(task)
    await session.commit()
    await session.refresh(project)

    proj_read = ProjectRead.model_validate(project)
    await publish(session_id, "project.created", {"project": proj_read.model_dump(mode="json")})
    await publish(session_id, "task.deleted", {"id": task_id})
    return proj_read

from datetime import UTC, datetime

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from vox_pm.events.bus import publish
from vox_pm.models import Task
from vox_pm.schemas import TaskRead


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
    query = select(Task.position).order_by(Task.position.desc())
    if project_id is not None:
        query = query.where(Task.project_id == project_id)
    result = await session.exec(query.limit(1))
    last = result.first()
    return (last or 0) + 1


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
    for field, value in kwargs.items():
        if value is not None and hasattr(task, field):
            setattr(task, field, value)
            changed.append(field)
    task.updated_at = datetime.now(UTC)
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
    task.project_id = project_id
    task.position = await _next_position(session, project_id)
    task.updated_at = datetime.now(UTC)
    session.add(task)
    await session.commit()
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

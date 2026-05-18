"""Reminder storage only — no delivery in v1."""

from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from vox_pm.models import Task


async def set_reminder(
    session: AsyncSession,
    task_id: str,
    remind_at: datetime,
) -> bool:
    task = await session.get(Task, task_id)
    if not task:
        return False
    task.reminder_at = remind_at
    session.add(task)
    await session.commit()
    return True


async def get_upcoming_reminders(session: AsyncSession, before: datetime) -> list[Task]:
    result = await session.exec(
        select(Task).where(Task.reminder_at <= before, Task.reminder_at != None)
    )
    return list(result.all())

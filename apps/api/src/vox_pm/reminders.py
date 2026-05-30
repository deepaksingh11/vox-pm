"""Reminder delivery worker.

A lightweight asyncio polling loop (started in the FastAPI lifespan) that fires
each task's `reminder_at` exactly once by flipping `reminder_fired`. No external
scheduler dependency — for a single-node demo this is the APScheduler equivalent.

Reminders are broadcast to every connected session: the current model has no
per-user ownership on tasks. Storing the owning client_id on the task and routing
to it is noted as future work.
"""

import asyncio
from datetime import UTC, datetime

from loguru import logger
from sqlmodel import col, select

from vox_pm.db import get_session_factory
from vox_pm.events.bus import broadcast
from vox_pm.models import Task
from vox_pm.schemas import TaskRead

_POLL_INTERVAL_SECONDS = 15


async def _run_once() -> int:
    """Fire all due, un-fired reminders. Returns the number fired.

    Factored out of the loop so tests can drive a single tick without sleeping.
    """
    # Match the naive-UTC storage convention used across the codebase (see models._now).
    now = datetime.now(UTC).replace(tzinfo=None)
    factory = get_session_factory()
    fired = 0
    async with factory() as db:
        stmt = select(Task).where(
            col(Task.reminder_at).is_not(None),
            Task.reminder_at <= now,  # type: ignore[operator]
            col(Task.reminder_fired).is_(False),
        )
        due = (await db.exec(stmt)).all()
        for task in due:
            read = TaskRead.model_validate(task)
            delivered = await broadcast("reminder.fired", {"task": read.model_dump(mode="json")})
            # Only mark fired once at least one client received it — otherwise leave it
            # due so it delivers when a client (re)connects, rather than being lost.
            if delivered > 0:
                task.reminder_fired = True
                db.add(task)
                fired += 1
        if fired:
            await db.commit()
    return fired


async def reminder_loop(stop: asyncio.Event) -> None:
    """Poll for due reminders every _POLL_INTERVAL_SECONDS until `stop` is set."""
    logger.info("reminder worker started")
    while not stop.is_set():
        try:
            count = await _run_once()
            if count:
                logger.info(f"reminder worker fired {count} reminder(s)")
        except Exception as exc:  # never let one bad tick kill the loop
            logger.warning(f"reminder tick failed: {exc}")
        # Wake early if stop is set during the interval.
        try:
            await asyncio.wait_for(stop.wait(), timeout=_POLL_INTERVAL_SECONDS)
        except TimeoutError:
            pass
    logger.info("reminder worker stopped")

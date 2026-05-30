"""Reminder delivery worker (#1)."""

from datetime import UTC, datetime, timedelta

import pytest

from vox_pm.events import bus
from vox_pm.models import Task
from vox_pm.reminders import _run_once


@pytest.fixture
def subscriber():
    q = bus.subscribe("client-1")
    yield q
    bus.unsubscribe("client-1", q)


@pytest.mark.asyncio
async def test_due_reminder_fires_once(db_session, subscriber):
    past = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    task = Task(title="Call finance", reminder_at=past)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    fired = await _run_once()
    assert fired == 1

    # Broadcast reached the subscriber with the task payload.
    event = subscriber.get_nowait()
    assert event.type == "reminder.fired"
    assert event.data["task"]["id"] == task.id

    # Flag persisted.
    row = await db_session.get(Task, task.id)
    assert row is not None and row.reminder_fired is True

    # Second tick fires nothing (idempotent delivery).
    assert await _run_once() == 0
    assert subscriber.empty()


@pytest.mark.asyncio
async def test_future_reminder_does_not_fire(db_session, subscriber):
    future = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
    task = Task(title="Later", reminder_at=future)
    db_session.add(task)
    await db_session.commit()

    assert await _run_once() == 0
    assert subscriber.empty()


@pytest.mark.asyncio
async def test_no_reminder_set_does_not_fire(db_session, subscriber):
    db_session.add(Task(title="No reminder"))
    await db_session.commit()

    assert await _run_once() == 0
    assert subscriber.empty()

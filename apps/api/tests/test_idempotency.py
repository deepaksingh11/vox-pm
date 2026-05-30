"""create_task idempotency under retry (#3)."""

import pytest
from sqlmodel import func, select

from vox_pm.agent.tools import dispatch_tool
from vox_pm.models import Task


async def dispatch(name: str, args: dict, session_id: str = "test"):
    return await dispatch_tool(name, args, session_id)


async def _task_count(db) -> int:
    return (await db.exec(select(func.count()).select_from(Task))).one()


@pytest.mark.asyncio
async def test_duplicate_create_within_window_dedupes(db_session):
    first = await dispatch("create_task", {"title": "Finance numbers"})
    second = await dispatch("create_task", {"title": "Finance numbers"})

    assert first["ok"] is True
    assert second["ok"] is True
    assert second.get("deduped") is True
    assert second["id"] == first["id"]
    # Exactly one row in the DB.
    assert await _task_count(db_session) == 1


@pytest.mark.asyncio
async def test_dedupe_scoped_by_project(db_session):
    proj_a = await dispatch("create_project", {"title": "Proj A"})
    proj_b = await dispatch("create_project", {"title": "Proj B"})
    a = await dispatch("create_task", {"title": "Same name", "project_id": proj_a["id"]})
    b = await dispatch("create_task", {"title": "Same name", "project_id": proj_b["id"]})

    # Same title but different project bucket → not a dedupe.
    assert b.get("deduped") is not True
    assert b["id"] != a["id"]
    assert await _task_count(db_session) == 2


@pytest.mark.asyncio
async def test_dedupe_scoped_by_session(db_session):
    a = await dispatch("create_task", {"title": "Cross session"}, session_id="s1")
    b = await dispatch("create_task", {"title": "Cross session"}, session_id="s2")

    # Different sessions have independent dedupe caches.
    assert b.get("deduped") is not True
    assert b["id"] != a["id"]
    assert await _task_count(db_session) == 2

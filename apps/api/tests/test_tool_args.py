"""Validation of LLM-emitted tool arguments before dispatch (#2)."""

import pytest
from sqlmodel import func, select

from vox_pm.agent.tools import dispatch_tool
from vox_pm.models import Task


async def dispatch(name: str, args: dict, session_id: str = "test"):
    return await dispatch_tool(name, args, session_id)


async def _task_count(db) -> int:
    return (await db.exec(select(func.count()).select_from(Task))).one()


@pytest.mark.asyncio
async def test_create_task_rejects_non_string_title(db_session):
    result = await dispatch("create_task", {"title": 123})
    assert result["ok"] is False
    assert "invalid arguments" in result["error"]
    # No row should have been written.
    assert await _task_count(db_session) == 0


@pytest.mark.asyncio
async def test_update_task_rejects_bad_status(db_session):
    created = await dispatch("create_task", {"title": "Real task"})
    result = await dispatch("update_task", {"id": created["id"], "status": "frozen"})
    assert result["ok"] is False
    assert "status" in result["error"]
    # Status must be unchanged on the persisted row.
    row = await db_session.get(Task, created["id"])
    assert row is not None and row.status == "open"


@pytest.mark.asyncio
async def test_unknown_field_rejected(db_session):
    result = await dispatch("create_task", {"title": "ok", "frobnicate": True})
    assert result["ok"] is False
    assert await _task_count(db_session) == 0


@pytest.mark.asyncio
async def test_valid_args_still_pass(db_session):
    result = await dispatch(
        "create_task",
        {"title": "Valid", "urgent": True, "due_at": "2026-06-01T09:00:00Z"},
    )
    assert result["ok"] is True
    assert await _task_count(db_session) == 1

"""Interruption durability (#4): a barge-in must not lose an in-flight write.

Pipecat cancels the tool handler on an InterruptionFrame. The handler awaits the
dispatch *shielded*, so the DB write completes anyway. These tests assert that
contract directly (the full pipeline interruption can't be driven in a unit test).
"""

import asyncio

import pytest
from sqlmodel import func, select

from vox_pm.agent.tools import dispatch_tool
from vox_pm.models import Project


async def dispatch(name: str, args: dict, session_id: str = "test"):
    return await dispatch_tool(name, args, session_id)


async def _project_count(db) -> int:
    return (await db.exec(select(func.count()).select_from(Project))).one()


@pytest.mark.asyncio
async def test_shielded_dispatch_survives_awaiter_cancellation(db_session):
    """Mirror the handler: dispatch runs as a task, awaited via asyncio.shield. Cancelling
    the awaiter (as Pipecat does on barge-in) must NOT abort the dispatch — the write lands."""
    task = asyncio.ensure_future(dispatch("create_project", {"title": "Survives barge-in"}))

    async def awaiter():
        await asyncio.shield(task)

    a = asyncio.ensure_future(awaiter())
    await asyncio.sleep(0)  # let the awaiter actually start awaiting the shield
    a.cancel()
    with pytest.raises(asyncio.CancelledError):
        await a

    # The shielded dispatch still runs to completion and the row persists.
    result = await task
    assert result["ok"] is True
    assert await _project_count(db_session) == 1


@pytest.mark.asyncio
async def test_retry_after_cancel_is_idempotent(db_session):
    """After a barge-in the LLM may re-issue the same create — it must not duplicate."""
    r1 = await dispatch("create_project", {"title": "Q2 report"})
    r2 = await dispatch("create_project", {"title": "Q2 report"})
    assert r1["ok"] and r2["ok"]
    assert r1["id"] == r2["id"]
    assert await _project_count(db_session) == 1

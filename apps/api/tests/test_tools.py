"""Tool dispatch integration tests.

Shared fixtures (db_session, patched session factory) live in conftest.py.
"""

import pytest
from sqlmodel import select

from vox_pm.models import Project, Task


async def dispatch(name: str, args: dict, session_id: str = "test"):
    from vox_pm.agent.tools import dispatch_tool
    return await dispatch_tool(name, args, session_id)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_project():
    result = await dispatch("create_project", {"title": "Q2 Report"})
    assert result["ok"] is True
    assert result["title"] == "Q2 Report"
    assert "id" in result


# ---------------------------------------------------------------------------
# Tasks — basic CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_task_without_project():
    result = await dispatch("create_task", {"title": "Draft intro"})
    assert result["ok"] is True
    assert result["title"] == "Draft intro"


@pytest.mark.asyncio
async def test_create_task_urgent():
    result = await dispatch("create_task", {"title": "Urgent task", "urgent": True})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_delete_task(db_session):
    created = await dispatch("create_task", {"title": "To delete"})
    task_id = created["id"]
    result = await dispatch("delete_task", {"id": task_id})
    assert result["ok"] is True
    # M2: verify row actually deleted
    assert await db_session.get(Task, task_id) is None


@pytest.mark.asyncio
async def test_delete_nonexistent_task():
    result = await dispatch("delete_task", {"id": "nonexistent"})
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# Tasks — update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_task(db_session):
    task = await dispatch("create_task", {"title": "Finance numbers"})
    result = await dispatch("update_task", {"id": task["id"], "urgent": True})
    assert result["ok"] is True
    # M2: verify field persisted
    row = await db_session.get(Task, task["id"])
    assert row is not None
    assert row.urgent is True


@pytest.mark.asyncio
async def test_update_task_clear_nullable(db_session):
    """M2/L2: clearing a nullable field via None must persist (not silently skip)."""
    task = await dispatch("create_task", {"title": "With desc", "description": "initial"})
    result = await dispatch("update_task", {"id": task["id"], "description": None})
    assert result["ok"] is True
    row = await db_session.get(Task, task["id"])
    assert row is not None
    assert row.description is None


# ---------------------------------------------------------------------------
# Tasks — move
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_move_task(db_session):
    project = await dispatch("create_project", {"title": "Target"})
    task = await dispatch("create_task", {"title": "Move me"})
    result = await dispatch("move_task", {"task_id": task["id"], "project_id": project["id"]})
    assert result["ok"] is True
    # M2: verify task.project_id actually changed
    row = await db_session.get(Task, task["id"])
    assert row is not None
    assert row.project_id == project["id"]
    assert row.position >= 1


@pytest.mark.asyncio
async def test_move_task_to_unassigned(db_session):
    """H2: moving to unassigned (NULL bucket) must not produce duplicate positions."""
    project = await dispatch("create_project", {"title": "Source"})
    t1 = await dispatch("create_task", {"title": "Task A", "project_id": project["id"]})
    t2 = await dispatch("create_task", {"title": "Task B", "project_id": project["id"]})
    # move both to unassigned
    r1 = await dispatch("move_task", {"task_id": t1["id"], "project_id": None})
    r2 = await dispatch("move_task", {"task_id": t2["id"], "project_id": None})
    assert r1["ok"] is True
    assert r2["ok"] is True
    # positions in the NULL bucket must be distinct
    row1 = await db_session.get(Task, t1["id"])
    row2 = await db_session.get(Task, t2["id"])
    assert row1 is not None and row2 is not None
    assert row1.position != row2.position


# ---------------------------------------------------------------------------
# Tasks — convert to project
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_convert_task_to_project(db_session):
    task = await dispatch("create_task", {"title": "Q2 Report"})
    task_id = task["id"]
    result = await dispatch("convert_task_to_project", {"task_id": task_id})
    assert result["ok"] is True
    assert result["title"] == "Q2 Report"
    # M2: original task must be deleted
    assert await db_session.get(Task, task_id) is None
    # M2: project must exist
    stmt = select(Project).where(Project.title == "Q2 Report")
    proj = (await db_session.exec(stmt)).first()
    assert proj is not None


@pytest.mark.asyncio
async def test_convert_task_to_project_duplicate_title(db_session):
    """M1: converting when a project with the same title exists must fail gracefully
    and leave the original task intact."""
    await dispatch("create_project", {"title": "Exists"})
    task = await dispatch("create_task", {"title": "Exists"})
    task_id = task["id"]
    result = await dispatch("convert_task_to_project", {"task_id": task_id})
    assert result["ok"] is False
    # M1: task must still exist
    assert await db_session.get(Task, task_id) is not None

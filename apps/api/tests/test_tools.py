"""Tool dispatch integration tests against in-memory SQLite."""

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import vox_pm.models  # noqa: F401


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def patch_session_factory(db_session, monkeypatch):
    import contextlib

    @contextlib.asynccontextmanager
    async def _cm():
        yield db_session

    class _Factory:
        def __call__(self):
            return _cm()

    import vox_pm.agent.tools as tools_mod
    monkeypatch.setattr(tools_mod, "get_session_factory", lambda: _Factory())


async def dispatch(name: str, args: dict, session_id: str = "test"):
    from vox_pm.agent.tools import dispatch_tool
    return await dispatch_tool(name, args, session_id)


@pytest.mark.asyncio
async def test_create_project():
    result = await dispatch("create_project", {"title": "Q2 Report"})
    assert result["ok"] is True
    assert result["title"] == "Q2 Report"
    assert "id" in result


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
async def test_delete_task():
    created = await dispatch("create_task", {"title": "To delete"})
    result = await dispatch("delete_task", {"id": created["id"]})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_delete_nonexistent_task():
    result = await dispatch("delete_task", {"id": "nonexistent"})
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_move_task():
    project = await dispatch("create_project", {"title": "Target"})
    task = await dispatch("create_task", {"title": "Move me"})
    result = await dispatch("move_task", {"task_id": task["id"], "project_id": project["id"]})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_convert_task_to_project():
    task = await dispatch("create_task", {"title": "Q2 Report"})
    result = await dispatch("convert_task_to_project", {"task_id": task["id"]})
    assert result["ok"] is True
    assert result["title"] == "Q2 Report"


@pytest.mark.asyncio
async def test_update_task():
    task = await dispatch("create_task", {"title": "Finance numbers"})
    result = await dispatch("update_task", {"id": task["id"], "urgent": True})
    assert result["ok"] is True

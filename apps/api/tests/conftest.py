"""Shared test fixtures.

Runs against SQLite in-memory by default. Set TEST_DATABASE_URL to a
postgresql+asyncpg:// URL for Postgres coverage.
"""

import contextlib
import os

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import vox_pm.models  # noqa: F401 — registers SQLModel metadata

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Modules that call get_session_factory() and must be redirected at the shared session.
_PATCH_TARGETS = ("vox_pm.agent.tools", "vox_pm.reminders")


@pytest.fixture(scope="function")
async def db_session():
    engine = create_async_engine(_TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    # Drop tables so each test starts fresh (matters for a shared Postgres DB in CI).
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
def patch_session_factory(db_session, monkeypatch):
    @contextlib.asynccontextmanager
    async def _cm():
        yield db_session

    class _Factory:
        def __call__(self):
            return _cm()

    import importlib

    for target in _PATCH_TARGETS:
        mod = importlib.import_module(target)
        monkeypatch.setattr(mod, "get_session_factory", lambda: _Factory())


@pytest.fixture(autouse=True)
def reset_session_state():
    # Per-session alias map + create-dedupe cache are module-global; clear between tests
    # so one test's state can't leak into the next (e.g. dedupe a fresh-DB create).
    import vox_pm.agent.state as state_mod

    state_mod._states.clear()
    yield
    state_mod._states.clear()

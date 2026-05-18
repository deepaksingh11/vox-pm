from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from vox_pm.config import get_settings

_engine = None
_session_factory = None


def _build_engine():
    settings = get_settings()
    url = settings.database_url
    # asyncpg doesn't accept sslmode/channel_binding as URL params — strip and pass via connect_args
    connect_args = {}
    for param in ("sslmode=require", "channel_binding=require"):
        url = url.replace(f"?{param}", "").replace(f"&{param}", "")
    if "neon.tech" in url or "sslmode" in settings.database_url:
        connect_args["ssl"] = True
    return create_async_engine(
        url,
        echo=False,
        pool_size=10,
        max_overflow=5,
        pool_timeout=10,
        connect_args=connect_args,
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def create_tables():
    async with get_engine().begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session

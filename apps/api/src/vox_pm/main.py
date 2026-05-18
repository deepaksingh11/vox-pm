import asyncio
import contextlib
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vox_pm.config import get_settings
from vox_pm.db import create_tables, get_session_factory
from vox_pm.routers import projects, tasks, voice
from vox_pm.events.ws import router as ws_router


_started_at = 0.0


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global _started_at
    _started_at = time.time()
    await create_tables()
    # warm up connection pool — prevents cold-start lag on first tool call
    async with get_session_factory()() as db:
        await db.exec(  # type: ignore[attr-defined]
            __import__("sqlalchemy", fromlist=["text"]).text("SELECT 1")
        )
    print("\n\033[36m[api]\033[0m  API ready", flush=True)
    print("\033[36m[api]\033[0m  http://localhost:8000", flush=True)
    print("\033[36m[api]\033[0m  http://localhost:8000/docs  (Swagger)\n", flush=True)
    try:
        yield
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vox PM API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
    app.include_router(voice.router, prefix="/api/voice", tags=["voice"])
    app.include_router(ws_router, tags=["events"])

    @app.get("/", tags=["health"])
    async def health():
        uptime = round(time.time() - _started_at, 1)
        return {"status": "ok", "uptime_seconds": uptime, "docs": "/docs"}

    return app


app = create_app()

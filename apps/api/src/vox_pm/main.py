import contextlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vox_pm.config import get_settings
from vox_pm.db import create_tables
from vox_pm.routers import projects, tasks, voice
from vox_pm.events.ws import router as ws_router


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


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

    return app


app = create_app()

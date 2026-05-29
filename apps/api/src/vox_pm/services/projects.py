from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, update

from vox_pm.events.bus import publish
from vox_pm.models import Project, Task
from vox_pm.schemas import ProjectRead


async def list_projects(session: AsyncSession) -> list[ProjectRead]:
    result = await session.exec(select(Project).order_by(Project.created_at))
    return [ProjectRead.model_validate(p) for p in result.all()]


async def get_project(session: AsyncSession, project_id: str) -> Project | None:
    return await session.get(Project, project_id)


async def create_project(
    session: AsyncSession,
    title: str,
    session_id: str = "default",
) -> ProjectRead:
    existing = await session.exec(select(Project).where(Project.title == title))
    if project := existing.first():
        return ProjectRead.model_validate(project)

    project = Project(title=title)
    session.add(project)
    try:
        await session.commit()
    except IntegrityError:
        # M7: concurrent request won the uq_projects_title race — fetch the winner
        await session.rollback()
        result = await session.exec(select(Project).where(Project.title == title))
        project = result.first()
        return ProjectRead.model_validate(project)

    await session.refresh(project)
    read = ProjectRead.model_validate(project)
    await publish(session_id, "project.created", {"project": read.model_dump(mode="json")})
    return read


async def update_project(
    session: AsyncSession,
    project_id: str,
    title: str | None = None,
    session_id: str = "default",
) -> ProjectRead | None:
    project = await session.get(Project, project_id)
    if not project:
        return None
    if title is not None:
        project.title = title
    project.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    read = ProjectRead.model_validate(project)
    await publish(session_id, "project.updated", {"project": read.model_dump(mode="json")})
    return read


async def delete_project(
    session: AsyncSession,
    project_id: str,
    session_id: str = "default",
) -> bool:
    project = await session.get(Project, project_id)
    if not project:
        return False
    await session.exec(update(Task).where(Task.project_id == project_id).values(project_id=None))
    await session.delete(project)
    await session.commit()
    await publish(session_id, "project.deleted", {"id": project_id})
    return True

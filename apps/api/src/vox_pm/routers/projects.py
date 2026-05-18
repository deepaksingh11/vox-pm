from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from vox_pm.db import get_session
from vox_pm.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from vox_pm.services import projects as svc

router = APIRouter()


@router.get("", response_model=list[ProjectRead])
async def list_projects(db: AsyncSession = Depends(get_session)):
    return await svc.list_projects(db)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: str, db: AsyncSession = Depends(get_session)):
    project = await svc.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404)
    return ProjectRead.model_validate(project)


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_session)):
    return await svc.create_project(db, body.title)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: str, body: ProjectUpdate, db: AsyncSession = Depends(get_session)
):
    result = await svc.update_project(db, project_id, title=body.title)
    if not result:
        raise HTTPException(status_code=404)
    return result


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, db: AsyncSession = Depends(get_session)):
    ok = await svc.delete_project(db, project_id)
    if not ok:
        raise HTTPException(status_code=404)

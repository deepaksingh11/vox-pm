from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from vox_pm.db import get_session
from vox_pm.schemas import TaskCreate, TaskRead, TaskUpdate
from vox_pm.services import tasks as svc

router = APIRouter()


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    project_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
):
    return await svc.list_tasks(db, project_id=project_id)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: str, db: AsyncSession = Depends(get_session)):
    task = await svc.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskRead.model_validate(task)


@router.post("", response_model=TaskRead, status_code=201)
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_session)):
    return await svc.create_task(
        db,
        title=body.title,
        project_id=body.project_id,
        description=body.description,
        urgent=body.urgent,
        due_at=body.due_at,
        reminder_at=body.reminder_at,
    )


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(task_id: str, body: TaskUpdate, db: AsyncSession = Depends(get_session)):
    # exclude_unset so explicit null clears nullable fields; exclude_none would drop them
    fields = body.model_dump(exclude_unset=True)

    if not fields:
        task = await svc.get_task(db, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskRead.model_validate(task)

    result: TaskRead | None = None

    # project_id must go through move_task to recompute position; direct setattr skips it
    if "project_id" in fields:
        result = await svc.move_task(db, task_id, fields.pop("project_id"))
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

    if fields:
        result = await svc.update_task(db, task_id, **fields)
        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

    if result is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_session)):
    ok = await svc.delete_task(db, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")

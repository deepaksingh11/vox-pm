"""Voice session lifecycle: create Daily room, start Pipecat pipeline."""

import asyncio
import uuid

import httpx
from fastapi import APIRouter, HTTPException

from vox_pm.agent.pipeline import run_pipeline
from vox_pm.config import get_settings
from vox_pm.schemas import SessionCreateResponse

router = APIRouter()

# Track running sessions so we can cancel on explicit disconnect
_active_sessions: dict[str, asyncio.Task] = {}


async def _create_daily_room(api_key: str) -> tuple[str, str]:
    """Creates a Daily room and returns (room_url, bot_token)."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.daily.co/v1/rooms",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"properties": {"exp": int(asyncio.get_event_loop().time()) + 3600}},
            timeout=10,
        )
        r.raise_for_status()
        room = r.json()
        room_url = room["url"]
        room_name = room["name"]

        # Mint a bot token with owner privileges
        t = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"properties": {"room_name": room_name, "is_owner": True}},
            timeout=10,
        )
        t.raise_for_status()
        token = t.json()["token"]

    return room_url, token


@router.post("/session", response_model=SessionCreateResponse)
async def create_session():
    settings = get_settings()
    if not settings.daily_api_key:
        raise HTTPException(status_code=503, detail="Daily API key not configured")

    try:
        room_url, token = await _create_daily_room(settings.daily_api_key)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Daily API error: {e}") from e

    session_id = str(uuid.uuid4())

    pipeline_task = asyncio.create_task(
        run_pipeline(session_id, room_url, token),
        name=f"pipeline-{session_id}",
    )
    _active_sessions[session_id] = pipeline_task

    def _cleanup(t: asyncio.Task):
        _active_sessions.pop(session_id, None)

    pipeline_task.add_done_callback(_cleanup)

    return SessionCreateResponse(session_id=session_id, room_url=room_url, token=token)


@router.delete("/session/{session_id}", status_code=204)
async def end_session(session_id: str):
    task = _active_sessions.pop(session_id, None)
    if task and not task.done():
        task.cancel()

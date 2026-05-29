"""Voice session lifecycle: create Daily room, start Pipecat pipeline."""

import asyncio
import time

import httpx
from fastapi import APIRouter, HTTPException
from loguru import logger

from vox_pm.agent.pipeline import run_pipeline
from vox_pm.config import get_settings
from vox_pm.schemas import SessionCreateRequest, SessionCreateResponse

router = APIRouter()

_active_sessions: dict[str, asyncio.Task] = {}
_session_rooms: dict[str, str] = {}  # session_id → room_name for cleanup


async def _delete_daily_room(api_key: str, room_name: str) -> None:
    try:
        async with httpx.AsyncClient() as client:
            await client.delete(
                f"https://api.daily.co/v1/rooms/{room_name}",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
    except Exception as exc:
        logger.warning(f"Failed to delete Daily room {room_name}: {exc}")


async def _create_daily_room(api_key: str) -> tuple[str, str, str, str]:
    """Returns (room_url, bot_token, user_token, room_name)."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.daily.co/v1/rooms",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"properties": {"exp": int(time.time()) + 3600}},
            timeout=10,
        )
        r.raise_for_status()
        room = r.json()
        room_url = room["url"]
        room_name = room["name"]

        bot_t = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"properties": {"room_name": room_name, "is_owner": True, "user_name": "Vox PM Bot"}},
            timeout=10,
        )
        bot_t.raise_for_status()
        bot_token = bot_t.json()["token"]

        user_t = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"properties": {"room_name": room_name, "user_name": "User"}},
            timeout=10,
        )
        user_t.raise_for_status()
        user_token = user_t.json()["token"]

    return room_url, bot_token, user_token, room_name


@router.post("/session", response_model=SessionCreateResponse)
async def create_session(body: SessionCreateRequest):
    # Use the client-supplied id as the event channel so REST, voice, and WS all publish to the same bucket.
    client_id = body.client_id
    settings = get_settings()
    if not settings.daily_api_key:
        raise HTTPException(status_code=503, detail="Daily API key not configured")

    # Prevent duplicate sessions for the same client (e.g. rapid double-click).
    if client_id in _active_sessions and not _active_sessions[client_id].done():
        raise HTTPException(status_code=409, detail="Session already active for this client")

    try:
        room_url, bot_token, user_token, room_name = await _create_daily_room(settings.daily_api_key)
    except httpx.HTTPError:
        # Don't expose raw httpx error: it may contain the request URL or auth headers.
        raise HTTPException(status_code=502, detail="Voice service unavailable") from None

    _session_rooms[client_id] = room_name

    pipeline_task = asyncio.create_task(
        run_pipeline(client_id, room_url, bot_token),
        name=f"pipeline-{client_id}",
    )
    _active_sessions[client_id] = pipeline_task

    def _cleanup(t: asyncio.Task):
        _active_sessions.pop(client_id, None)
        room = _session_rooms.pop(client_id, None)
        if room:
            # Keep a strong ref so the task isn't GC'd before the DELETE completes.
            cleanup_task = asyncio.create_task(
                _delete_daily_room(settings.daily_api_key, room),
                name=f"room-cleanup-{client_id}",
            )
            cleanup_task.add_done_callback(lambda _: None)  # prevent GC
        exc = t.exception() if not t.cancelled() else None
        if exc is not None:
            import traceback
            print(f"\n[pipeline error] session={client_id}")
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    pipeline_task.add_done_callback(_cleanup)

    return SessionCreateResponse(session_id=client_id, room_url=room_url, token=user_token)


@router.delete("/session/{session_id}", status_code=204)
async def end_session(session_id: str):
    task = _active_sessions.pop(session_id, None)
    if task and not task.done():
        task.cancel()
    # Room deletion happens in _cleanup callback once the task finishes cancelling

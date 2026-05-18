"""WebSocket endpoint: /ws/events?session_id=..."""

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vox_pm.events.bus import subscribe, unsubscribe

router = APIRouter()


@router.websocket("/ws/events")
async def events_ws(websocket: WebSocket, session_id: str = "default"):
    await websocket.accept()
    q = subscribe(session_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30)
                await websocket.send_text(event.model_dump_json())
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        unsubscribe(session_id, q)

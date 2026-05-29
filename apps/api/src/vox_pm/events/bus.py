"""In-process pub/sub. Sessions publish typed events; WS gateway subscribes."""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime

from vox_pm.schemas import EventType, WSEvent


_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def subscribe(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    _subscribers[session_id].append(q)
    return q


def unsubscribe(session_id: str, q: asyncio.Queue) -> None:
    subs = _subscribers.get(session_id, [])
    if q in subs:
        subs.remove(q)
    if not subs:
        _subscribers.pop(session_id, None)


async def publish(session_id: str, event_type: EventType, data: dict) -> None:
    # Broadcast to all subscribers regardless of session_id.
    # REST routers publish to "default" while WS clients subscribe to voice-session UUIDs;
    # per-session routing silently dropped all REST-originated events.
    event = WSEvent(type=event_type, ts=datetime.now(UTC), data=data)
    dead: list[tuple[str, asyncio.Queue]] = []

    for sid, queues in list(_subscribers.items()):
        for q in list(queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # M2: drop oldest event to make room rather than permanently killing the subscriber.
                # A slow client losing one old event is better than losing all future events.
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    dead.append((sid, q))

    for sid, q in dead:
        unsubscribe(sid, q)

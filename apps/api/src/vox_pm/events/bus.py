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
    # Deliver only to subscribers registered under this session_id.
    # REST routers and voice pipeline both publish to the frontend clientId,
    # so events are scoped to the correct client without cross-session leaks.
    event = WSEvent(type=event_type, ts=datetime.now(UTC), data=data)
    dead: list[asyncio.Queue] = []

    for q in list(_subscribers.get(session_id, [])):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            # Drop oldest event to make room rather than permanently killing the subscriber.
            # A slow client losing one old event is better than losing all future events.
            try:
                q.get_nowait()
                q.put_nowait(event)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                dead.append(q)

    for q in dead:
        unsubscribe(session_id, q)


async def broadcast(event_type: EventType, data: dict) -> int:
    # Fan an event out to every connected session. Used by the reminder worker, which
    # has no single owning session in the current single-user model. list() snapshots
    # the keys so we don't mutate _subscribers (via publish→unsubscribe) mid-iteration.
    # Returns the number of sessions delivered to, so the caller can defer marking a
    # reminder "fired" until at least one client was actually listening.
    sessions = list(_subscribers.keys())
    for session_id in sessions:
        await publish(session_id, event_type, data)
    return len(sessions)

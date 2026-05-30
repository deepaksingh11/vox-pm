"""E2E-lite: tool dispatch → DB → WS event contract (#6).

Verifies the utterance-handler path emits the right bus event with the right
payload, which is what the frontend store reduces over.
"""

import pytest

from vox_pm.agent.tools import dispatch_tool
from vox_pm.events import bus


@pytest.fixture
def subscriber():
    q = bus.subscribe("client-e2e")
    yield q
    bus.unsubscribe("client-e2e", q)


@pytest.mark.asyncio
async def test_create_task_emits_task_created_event(db_session, subscriber):
    result = await dispatch_tool("create_task", {"title": "Draft intro"}, "client-e2e")
    assert result["ok"] is True

    event = subscriber.get_nowait()
    assert event.type == "task.created"
    assert event.data["task"]["title"] == "Draft intro"
    assert event.data["task"]["id"] == result["id"]


@pytest.mark.asyncio
async def test_move_task_emits_task_moved_event(db_session, subscriber):
    project = await dispatch_tool("create_project", {"title": "Dest"}, "client-e2e")
    task = await dispatch_tool("create_task", {"title": "Move me"}, "client-e2e")
    # Drain create events.
    while not subscriber.empty():
        subscriber.get_nowait()

    await dispatch_tool(
        "move_task", {"task_id": task["id"], "project_id": project["id"]}, "client-e2e"
    )
    event = subscriber.get_nowait()
    assert event.type == "task.moved"
    assert event.data["to_project_id"] == project["id"]

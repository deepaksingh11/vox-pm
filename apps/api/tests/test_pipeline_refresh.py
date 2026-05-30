"""Per-turn snapshot reconcile (#4 Fix 2): refresh_system_prompt rebuilds the system
message from the DB, so a committed-but-CANCELLED write becomes visible to the LLM on
the next user turn."""

import asyncio

import pytest
from pipecat.processors.aggregators.llm_context import LLMContext

from vox_pm.agent.pipeline import refresh_system_prompt
from vox_pm.agent.tools import dispatch_tool


@pytest.mark.asyncio
async def test_refresh_picks_up_committed_entity(db_session):
    session_id = "refresh-test"
    # Simulate the post-barge-in state: a project committed to the DB while the LLM's
    # system message is still stale (the tool result was marked CANCELLED).
    await dispatch_tool("create_project", {"title": "Personal stuff"}, session_id)

    context = LLMContext()
    context.add_message({"role": "system", "content": "WS: empty"})

    await refresh_system_prompt(session_id, context, asyncio.Lock())

    content = context.messages[0]["content"]
    assert "Personal stuff" in content
    assert context.messages[0]["role"] == "system"


@pytest.mark.asyncio
async def test_refresh_noop_when_no_system_message(db_session):
    # Defensive: refresh must not crash if messages[0] isn't a system message.
    context = LLMContext()
    context.add_message({"role": "user", "content": "hello"})
    await refresh_system_prompt("refresh-test-2", context, asyncio.Lock())
    assert context.messages[0]["content"] == "hello"

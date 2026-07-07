"""_trim_context must never orphan a tool_calls/tool-result pair.

The universal LLMContext stores messages in OpenAI chat format: an assistant
message carrying `tool_calls` is followed by one or more `role: "tool"` result
messages. Providers (Anthropic in particular) reject a prompt where a tool
result appears without its originating tool_calls message, so the trim cut
point must always land on a plain user message.
"""

from pipecat.processors.aggregators.llm_context import LLMContext

from vox_pm.agent.pipeline import _MAX_CONTEXT_MESSAGES, _trim_context


def _system() -> dict:
    return {"role": "system", "content": "sys"}


def _user(i: int) -> dict:
    return {"role": "user", "content": f"u{i}"}


def _assistant_tool_call(i: int) -> dict:
    return {
        "role": "assistant",
        "tool_calls": [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": "create_task", "arguments": "{}"},
            }
        ],
    }


def _tool_result(i: int) -> dict:
    return {"role": "tool", "tool_call_id": f"call_{i}", "content": '{"ok": true}'}


def _assistant(i: int) -> dict:
    return {"role": "assistant", "content": f"a{i}"}


def _make_context(messages: list[dict]) -> LLMContext:
    ctx = LLMContext()
    for m in messages:
        ctx.add_message(m)
    return ctx


def test_no_trim_under_limit():
    msgs = [_system()] + [_user(i) for i in range(_MAX_CONTEXT_MESSAGES)]
    ctx = _make_context(msgs)
    _trim_context(ctx)
    assert len(ctx.messages) == len(msgs)


def test_trim_keeps_system_and_cuts_at_user_boundary():
    # Long history of user / tool-call / tool-result / assistant turns.
    msgs = [_system()]
    for i in range(30):
        msgs += [_user(i), _assistant_tool_call(i), _tool_result(i), _assistant(i)]
    ctx = _make_context(msgs)
    _trim_context(ctx)

    out = ctx.messages
    assert out[0]["role"] == "system"
    # Cut boundary is a plain user message — never an orphaned tool result.
    assert out[1]["role"] == "user"
    assert len(out) < len(msgs)


def test_trim_never_orphans_tool_result():
    # Arrange the tail so the naive cut point (len - _MAX_CONTEXT_MESSAGES) lands
    # exactly on a role:"tool" message.
    msgs = [_system()]
    i = 0
    while len(msgs) < 3 * _MAX_CONTEXT_MESSAGES:
        msgs += [_user(i), _assistant_tool_call(i), _tool_result(i), _assistant(i)]
        i += 1
    ctx = _make_context(msgs)
    _trim_context(ctx)

    out = ctx.messages
    seen_call_ids: set[str] = set()
    for m in out:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            seen_call_ids.update(tc["id"] for tc in m["tool_calls"])
        if m.get("role") == "tool":
            assert m["tool_call_id"] in seen_call_ids, "orphaned tool result after trim"


def test_trim_skips_when_no_safe_boundary():
    # Pathological tail with no user message after the naive cut point: trim must
    # leave the context intact rather than orphan a pair.
    msgs = [_system(), _user(0)]
    for i in range(_MAX_CONTEXT_MESSAGES + 10):
        msgs += [_assistant_tool_call(i), _tool_result(i)]
    ctx = _make_context(msgs)
    before = len(ctx.messages)
    _trim_context(ctx)
    assert len(ctx.messages) == before

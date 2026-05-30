# Agent Module

Pipecat pipeline + LLM orchestration for the voice PM agent.

## Pipeline flow

```
DailyTransport (input audio)
  → DeepgramSTTService (nova-3, interim_results=True, endpointing=300ms)
  → _TranscriptPublisher    ← publishes transcript.partial / transcript.final to event bus
  → LLMUserContextAggregator
  → AnthropicLLMService     ← Claude Sonnet 4.6, tool handlers registered per tool name
  → CartesiaTTSService
  → DailyTransport (output audio)
  → LLMAssistantContextAggregator
```

`allow_interruptions=True` on PipelineTask — user speech cuts TTS mid-sentence.

`_TranscriptPublisher` holds strong refs to all in-flight `asyncio.Task` objects (in `self._tasks`) so they can't be GC'd mid-flight. Exceptions inside `publish()` are logged via a done-callback.

## Tool dispatch flow

```
LLM emits tool call
  → _make_tool_handler() in pipeline.py (single FunctionCallParams arg, Pipecat 1.2+ API)
  → publish tool.started event
  → asyncio.wait_for(asyncio.shield(dispatch_tool(...)), timeout=30s)   ← shield: a barge-in can't abandon the write mid-commit
      → validate args against per-tool pydantic model (tool_args.py, extra="forbid")
          → bad type / invalid status enum / unknown field → return {"ok":False, "error":"invalid arguments ..."}
      → resolve short aliases (P1/T1) → full UUIDs via SessionState
          → unknown alias (P\d+/T\d+ not in map) → return {"ok":False, "error":"unknown reference"}
          → full UUID → pass through unchanged
      → call service (projects.py / tasks.py)
      → service mutates DB + publishes domain event to bus
  → publish tool.completed / tool.failed / tool.timeout event
  → refresh_system_prompt(): rebuild snapshot from DB (also runs at the START of each user
      turn, in _TranscriptPublisher, so an interrupted-but-committed write reconciles next turn)
  → trim context to MAX_CONTEXT_MESSAGES=40 (keeps system message + last 40 messages)
  → result_callback(result) → LLM continues turn
  → repeat for all tool calls in sequence
  → LLM produces spoken response only after all tools complete
```

## Reference resolution

`state.py` — `SessionState` per session (in-memory, keyed by session_id). Cleared in `finally` block of `run_pipeline` to prevent memory leak and stale-alias bleed across sessions.

Snapshot format injected into system prompt:
```
WS:
P1 "Q2 report"
  T1 "Draft the intro"
  T2 "Get numbers from finance"!  due=2026-05-22
P2 "Q2 review"
  T3 "Review with Sarah"
^T T2 "Get numbers from finance"   ← last touched
```

**Aliases are stable for the entire session lifetime.** `P1` assigned on first snapshot is `P1` forever — even if the entity is deleted, even if other entities are added. Aliases are never cleared or renumbered. This prevents the LLM from deleting the wrong entity when the alias map shifts between turns.

`resolve_id()` returns `None` for alias-shaped strings (`P\d+`/`T\d+`) not in the map; `dispatch_tool` treats this as an error and returns `{"ok": False, "error": "unknown reference ..."}` before touching the DB.

`SessionState.recent` — rolling deque (max 20) of touched entities. Last entry = "it"/"that".

## System prompt

`prompts.py` — injected at session start, refreshed after each tool call AND at the start of each user turn (so the LLM always sees current DB state). Includes current UTC date+time for relative-time resolution ("in 1 minute").

Key rules enforced via prompt:
- Execute ALL tool calls before any spoken response
- Today's UTC date for relative date resolution ("Friday" → upcoming Friday 00:00 UTC)
- Sentence-case titles
- Fuzzy reference resolution ("the finance one" → T2)
- `ask_clarification` only when ref truly unresolvable AND action irreversible

## LLM provider selection

`llm/factory.py` — walks `LLM_PROVIDERS` env var (default: `anthropic,gemini,openai`). First entry with a valid API key wins. All providers register identical function handlers against the same `TOOL_DEFINITIONS` / `TOOLS_SCHEMA`.

## Argument validation

Every tool call is validated against a per-tool pydantic model in `tool_args.py` (`ARG_MODELS`, `extra="forbid"`) before reference resolution or any DB work. This keeps malformed LLM output (wrong types, hallucinated fields, invalid `status`) out of the service layer and returns a readable error the model can correct against. Dates stay as strings — `_parse_dt` owns ISO 8601 + timezone normalization.

## Idempotency

`create_project` checks for an existing title before inserting; on concurrent race (TOCTOU), catches `IntegrityError` on commit, rolls back, and re-fetches the winner. Prevents duplicate projects when LLM retries after a cancelled tool result (mid-utterance interruption).

`create_task` dedupes on `(title, project_id)` within an 8 s window per session via `SessionState.check_recent_create` / `record_create`. A retried create (same interruption scenario) returns the existing task with `deduped: true` instead of inserting a duplicate. Time-boxed rather than a unique constraint, because task titles legitimately repeat.

## Interruption handling

`PipelineTask(allow_interruptions=True)` — if the user speaks while TTS is playing, audio is cut and the new transcript is processed immediately. Pipecat cancels in-flight tool tasks on the interruption, which would otherwise abandon a write mid-commit. Two guards (in `pipeline.py`) make a barge-in safe:

1. **Shielded dispatch** — `handle` runs `dispatch_tool` as a task awaited via `asyncio.shield`. A handler cancellation (barge-in) no longer aborts the DB write or its entity WS event — they run to completion. `except asyncio.CancelledError` logs and re-raises so Pipecat unwinds cleanly. A genuine 30 s timeout still `task.cancel()`s the hung dispatch explicitly (shield only protects against external cancellation, not hangs).
2. **Per-turn reconcile** — `refresh_system_prompt()` runs at the start of every user turn (on the final `TranscriptionFrame` in `_TranscriptPublisher`), not only after a successful tool. So a tool Pipecat marked `CANCELLED` whose shielded write actually committed is reconciled into the LLM's view on the next turn. A prompt rule tells the model `CANCELLED` is indeterminate — trust the snapshot.

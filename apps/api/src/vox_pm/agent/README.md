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

## Tool dispatch flow

```
LLM emits tool call
  → _make_tool_handler() in pipeline.py (single FunctionCallParams arg, Pipecat 1.2+ API)
  → publish tool.started event
  → dispatch_tool(name, args, session_id) in tools.py
      → resolve short aliases (P1/T1) → full UUIDs via SessionState._alias_map
      → call service (projects.py / tasks.py)
      → service mutates DB + publishes domain event to bus
  → publish tool.completed / tool.failed event
  → refresh system prompt snapshot (runs even on failure)
  → result_callback(result) → LLM continues turn
  → repeat for all tool calls in sequence
  → LLM produces spoken response only after all tools complete
```

## Reference resolution

`state.py` — `SessionState` per session (in-memory, keyed by session_id).

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

Aliases (P1, T2) map to full UUIDs. LLM uses these for tool args; `resolve_id()` converts back before DB call.

`SessionState.recent` — rolling deque (max 20) of touched entities. Last entry = "it"/"that".

## System prompt

`prompts.py` — injected at session start, refreshed after each tool call.

Key rules enforced via prompt:
- Execute ALL tool calls before any spoken response
- Today's UTC date for relative date resolution ("Friday" → upcoming Friday 00:00 UTC)
- Sentence-case titles
- Fuzzy reference resolution ("the finance one" → T2)
- `ask_clarification` only when ref truly unresolvable AND action irreversible

## LLM provider selection

`llm/factory.py` — walks `LLM_PROVIDERS` env var (default: `anthropic,gemini,openai`). First entry with a valid API key wins. All providers register identical function handlers against the same tool definitions.

## Idempotency

`create_project` returns existing project if a project with the same title already exists. Prevents duplicate projects when LLM retries after a cancelled tool result (mid-utterance interruption).

## Interruption handling

`PipelineTask(allow_interruptions=True)` — if user speaks while TTS is playing, audio is cut and the new transcript is processed immediately. The incomplete tool sequence from the interrupted turn is lost; the new utterance starts a fresh LLM turn.

# Vox PM — Submission Writeup

## TL;DR

**Problem**: Build a voice-first PM tool where the user speaks in long, messy utterances — corrections, interleaved intent, ambiguous references — and the UI reflects their intent in real time.

**What it does**: Vox PM listens via WebRTC microphone, transcribes speech with Deepgram, feeds the transcript to Claude Sonnet 4.6, which emits tool calls (create/update/delete projects & tasks, move, set urgency, due dates, reminders), executes them against Postgres, and pushes domain events over a WebSocket to a React UI that updates live as the agent works. The entire Q2-report example from the spec — corrections, mid-sentence moves, clarifications — runs end-to-end in a single utterance.

**Stack (one line)**:
Daily WebRTC → Pipecat → Deepgram STT → Claude Sonnet 4.6 → FastAPI + SQLModel + Neon Postgres → asyncio pub/sub → FastAPI WebSocket → React + Zustand

---

## 1. The Problem, Decomposed

Voice PM is harder than "talk to a chatbot" for four reasons:

| Sub-problem | Why it's hard | How Vox PM solves it |
|-------------|---------------|----------------------|
| Audio I/O + STT/TTS | WebRTC, VAD, streaming transcription, low-latency synthesis — don't reinvent | Pipecat frame-graph + Daily + Deepgram + Cartesia |
| Intent extraction from noisy speech | Long utterances, corrections, interleaved entity creation and metadata | Tool-calling LLM (Sonnet 4.6) with terse system prompt and strict sequencing rules |
| State + reference resolution | "it", "that", "the finance one", "the first task" must resolve correctly within a session | In-memory `SessionState` with alias map (P1/T3), recent-touched deque, workspace snapshot injected into every prompt |
| Real-time UI without polling | User expects immediate visual feedback, not a spinner | Server-push WebSocket event bus, separate from Daily's audio channel |

---

## 2. Architecture

```
Browser (React / Zustand)           API (FastAPI + Pipecat / asyncio)           External
──────────────────────              ────────────────────────────────             ────────
mic ──audio──► Daily WebRTC ───────► DailyTransport (audio_in/audio_out)
                                            │
                                     Silero VAD
                                            │
                                     Deepgram STT nova-3
                                     (interim_results, numerals, 300ms endpointing)
                                            │
                                     _TranscriptPublisher  ──► event bus ──► WS ──► LiveTranscript
                                            │
                                     LLMContextAggregator (user side)
                                            │
                                     Claude Sonnet 4.6  ◄──── system prompt
                                      │          │              (snapshot rebuilt each tool call)
                                      │          └─► tool dispatch ──► services/* ──► Neon Postgres
                                      │                                      │
                                      │                               event bus (asyncio.Queue)
                                      │                                      │
                                      │                               WS /ws/events ──► Zustand ──► React
                                      ▼
                                Cartesia TTS ──► transport.output ──► speaker
```

**Two channels between server and client:**
- **Daily WebRTC** — audio in/out only (mic → speaker).
- **Custom WebSocket** (`/ws/events?session_id=…`) — all state events: transcripts, tool calls, entity CRUD, clarifications.

No RTVI. RTVI's event vocabulary is designed for chat bots; Vox PM's state events are a domain protocol (project/task CRUD), and decoupling them from the audio framework means the UI can evolve independently.

**Tool dispatch is observable**: every call publishes `tool.started`, `tool.completed`, or `tool.failed` with `duration_ms`, so the action feed in the UI is never reconstructed from state — it's just rendered verbatim from the event stream.

---

## 3. Stack Choices

| Layer | Choice | Why |
|-------|--------|-----|
| Audio transport | Daily.co WebRTC | Pipecat-native; owner/participant room model; cheap ephemeral rooms |
| Voice framework | Pipecat 1.2+ | Frame-graph composition, built-in interruption support, provider-agnostic LLM/STT/TTS adapters |
| STT | Deepgram `nova-3` | Fast streaming, `interim_results=True` for live transcript UX, `numerals=True` prevents "Q two" in titles, 300 ms endpointing tunable |
| TTS | Cartesia | Sub-200 ms first-audio-chunk; streaming support |
| LLM | Claude Sonnet 4.6 (default) | Reliable multi-tool sequencing in a single turn; fallback chain: GPT-4o-mini, Gemini 2.0 Flash |
| Backend | FastAPI + SQLModel + asyncpg | Fully async; no ORM/asyncio impedance mismatch |
| DB | Postgres on Neon | Managed, free tier, direct asyncpg (no PgBouncer overhead) |
| Frontend | React + Zustand + Tailwind v4 + shadcn/Radix | Minimal overhead; Zustand keeps event handling out of component trees |
| Build | pnpm workspaces + uv + concurrently | `pnpm dev` starts both API and web in one terminal |

---

## 4. Key Design Decisions

### 4.1 Tool sequencing before speech
**What**: System prompt rule — identify ALL required tool calls, execute them in sequence, then speak. Never narrate between tools.

**Why**: Without this, Sonnet would say "OK, created the project. Now I'll add tasks…" after each tool. That fragments TTS into 4–5 short clips with silence gaps between them, which sounds broken. Batching all tools first, then confirming once, is both faster and more natural.

> File: `apps/api/src/vox_pm/agent/prompts.py`

---

### 4.2 Workspace snapshot rebuilt after every tool call
**What**: `_make_tool_handler` in `pipeline.py` mutates `context.messages[0]` (the system message) after each tool dispatch, injecting a fresh workspace summary from the DB.

**Why**: Without this, a multi-tool turn has stale state. The LLM creates "Q2 report" in tool call 1, then tries to add tasks to it in tool call 2 — but the snapshot still says the project doesn't exist. Rebuilding the snapshot after every call eliminates this class of bug at the cost of ~1 extra DB query per tool.

> File: `apps/api/src/vox_pm/agent/pipeline.py` → `_make_tool_handler`

---

### 4.3 Alias map (P1, T3) instead of UUIDs in the prompt
**What**: `SessionState` assigns short aliases (`P1`, `P2`, `T1`, `T3`, …) to every entity. The workspace snapshot uses these aliases. The LLM emits them in tool arguments; the server resolves them to UUIDs before the DB call. **Aliases are stable for the session lifetime** — once assigned, never renumbered even if earlier entities are deleted. Unknown alias-shaped args not in the map are rejected before touching the DB.

**Why**: UUIDs are 36 characters each. A workspace with 5 projects and 20 tasks would add ~1 KB of UUID noise to every prompt turn. Aliases cut that to ~40 characters. On long sessions with many tool calls, this meaningfully reduces cost and latency. Alias stability prevents the silent wrong-entity delete that occurs when the map shifts after a deletion.

```
WS:
P1 "Q2 report"
  T1 "Draft the intro"
  T2 "Get numbers from finance"!  due=2026-05-22
P2 "Q2 Review"
  T3 "Review with Sarah"
^T T2 "Get numbers from finance"
```

> File: `apps/api/src/vox_pm/agent/state.py` → `SessionState.snapshot_text()`

---

### 4.4 Correction semantics differentiated in the prompt
**What**: Prompt explicitly separates two correction words:
- `actually…` → replace prior intent; undo completed tool calls if they contradict the new intent.
- `wait…` → user is *appending* a correction to the remaining plan; never undo completed work.

**Why**: During testing, Sonnet treated "wait, move the review task to Q2 Review instead" as an "undo all" signal and deleted the Q2 Review project it had just created. Adding the explicit `wait ≠ undo` rule fixed it. The distinction between replacing vs. appending intent is subtle but critical for real speech patterns.

> File: `apps/api/src/vox_pm/agent/prompts.py`

---

### 4.5 Idempotent `create_project` — two-layer safety
**What**: `create_project` first does `SELECT WHERE title = X`; if a match exists, returns it without re-inserting or re-publishing. DB also has `UniqueConstraint("title")`. On a TOCTOU race (two concurrent creates both pass the SELECT), the loser catches `IntegrityError` on commit, rolls back, and re-fetches the winner — no 500, no duplicate.

**Why**: When a user interrupts mid-TTS (barge-in), the pipeline's current tool sequence is abandoned. If the LLM retried `create_project("Q2 report")` after reconnecting, it would create a duplicate. The SELECT is the fast path; the unique constraint + `IntegrityError` catch is the safety net for concurrent retries.

> File: `apps/api/src/vox_pm/services/projects.py` → `create_project`

---

### 4.6 `delete_project` reparents tasks, not cascade-delete
**What**: Before deleting a project row, the service runs `UPDATE tasks SET project_id = NULL WHERE project_id = X`. Tasks survive as unassigned orphans.

**Why**: Cascade-delete would silently destroy work the user still wants. Reparenting-to-NULL mirrors real PM tools (work survives container deletion). The frontend's `applyEvent` for `project.deleted` does the same null-out optimistically, so the two paths stay consistent.

> File: `apps/api/src/vox_pm/services/projects.py` → `delete_project`

---

### 4.7 In-process asyncio pub/sub
**What**: `events/bus.py` — `dict[session_id, list[asyncio.Queue(maxsize=256)]]`. `publish()` **broadcasts to every subscriber** (single global workspace — per-session routing caused REST mutations to land in the wrong bucket). On `QueueFull`, drops the oldest event from the queue and inserts the new one, keeping the subscriber alive rather than permanently evicting it.

**Why**: For a single-process, single-user app this is the right level of complexity — no Redis dependency, no serialization overhead, no network hop. The tradeoff (dies on horizontal scale) is acceptable for v1 and the replacement path is clear: swap `asyncio.Queue` for Redis Streams or NATS JetStream when needed.

> File: `apps/api/src/vox_pm/events/bus.py`

---

### 4.8 Connection pool tuned for Neon — no pooler, no pre-ping
**What**: Direct asyncpg connection (no `-pooler` suffix), `pool_size=10`, `max_overflow=5`, `pool_timeout=10s`, `echo=False`, no `pool_pre_ping`. Lifespan runs `SELECT 1` to warm the pool.

**Why**: Neon's PgBouncer pooler adds ~400 ms overhead vs. direct connections. `pool_pre_ping` sends a `SELECT 1` before every checkout — unnecessary latency for an app that already has a persistent pool. The lifespan warm-up eliminates the cold-start hit (was adding ~1.5 s to the first tool call after a server restart).

> File: `apps/api/src/vox_pm/db.py`

---

### 4.9 Provider-agnostic LLM factory
**What**: `LLM_PROVIDERS=anthropic,gemini,openai` (env-driven, default `anthropic`). `factory.py` walks the list and picks the first provider with a valid API key. All three register the same `ToolsSchema`.

**Why**: Easy A/B during development (swap LLMs by changing one env var); CI runs without any provider key; Anthropic is the default but not a hard dependency. In practice, Sonnet 4.6 was significantly more reliable at multi-tool sequencing than the alternatives during testing.

> File: `apps/api/src/vox_pm/agent/llm/factory.py`

---

### 4.10 Frontend resilience: ErrorBoundary + retry + safeFormat
**What**: Three defense layers:
- `ErrorBoundary` wraps `<App />` — render crash shows a "Reload app" screen instead of a blank page.
- `loadInitialState` retries 5× (300/600/900/1200 ms linear backoff) — absorbs the startup race where Vite mounts before uvicorn binds.
- `safeFormat` wraps every `date-fns` call with `isValid()` — invalid dates from the LLM don't crash the task row render.

**Why**: A voice agent emitting unexpected data (malformed dates, unknown event types) is not a recoverable error by default in React. These layers make the UI resilient to partial failures without hiding them.

> Files: `apps/web/src/components/ErrorBoundary.tsx`, `apps/web/src/hooks/useStore.ts`, `apps/web/src/components/TaskRow.tsx`

---

## 5. Voice-Specific Tradeoffs (camb.ai focus)

### 5.1 Latency budget

| Stage | Typical latency |
|-------|----------------|
| Mic → Daily → Deepgram interim | 150–300 ms |
| STT endpointing wait | 300 ms |
| LLM turn: 1 tool call (Sonnet 4.6) | 1.5–2.5 s |
| LLM turn: 3 tool calls | 2.5–4.5 s |
| DB round-trip (Neon, same region) | 50–200 ms per tool |
| Cartesia TTS first audio chunk | ~200 ms |
| **Total: single-tool command** | **~2.5 s** |
| **Total: 3–4 tool commands** | **~4–5 s** |

The system-prompt rule that batches all tools before speaking *adds* latency to the first sound but eliminates fragmented TTS. The tradeoff favors clarity over speed-to-first-byte.

### 5.2 Interim transcripts as UX latency hedge
`interim_results=True` on Deepgram means the "You: …" transcript bubble updates every ~150 ms as the user speaks. Even while the LLM is working, the user has visual confirmation they were heard. This is the cheapest perceived-latency win in the stack — costs nothing but a state update.

### 5.3 VAD + endpointing tradeoff
Silero VAD (`SileroVADAnalyzer`) detects speech boundaries in Pipecat's frame graph. Deepgram `endpointing=300` ms controls how long Deepgram waits for silence before finalizing a transcript. At 300 ms:
- Too low (e.g. 100 ms): cuts natural speech pauses within sentences ("Add a task… to finalize").
- Too high (e.g. 1000 ms): user stares at the UI waiting for a response on short commands.

300 ms is the Deepgram-recommended default for assistant applications and held up well in testing.

### 5.4 Interruptions are first-class
`PipelineParams(allow_interruptions=True)` — speaking while the bot is mid-TTS immediately cuts audio and starts a fresh LLM turn. Combined with idempotent `create_project`, a user can interrupt mid-confirmation and re-state their intent without creating duplicate state.

The incomplete tool sequence from an interrupted turn is simply dropped (Pipecat discards buffered TTS frames). The LLM context accumulates only completed turns.

### 5.5 Double-belt number normalization
Deepgram's `numerals=True` converts spoken digits ("Q two") to numerals ("Q 2") at the STT layer. The system prompt also has an explicit rule: "convert number words to digits in titles." Two independent layers because STT accuracy isn't 100% and the prompt rule catches any that slip through.

### 5.6 Token economy: terse system prompt
`prompts.py` is 15 lines. Every byte is paid for on every turn for every tool call. The workspace snapshot uses single-letter markers (`!` for urgent, `^T` for last-touched), 2-char aliases (`P1`, `T3`), and abbreviated ISO dates. A 5-project, 20-task workspace snapshot is ~200 tokens. A verbose version would be 800+.

### 5.7 No transcript persistence — intentional
Conversation history lives only in `LLMContext` for the pipeline's lifetime. Tradeoffs accepted: privacy (no voice content stored beyond the session), cost (no growing context), simplicity (no session recovery). For v2: persist transcripts to a `sessions` table; enable "what did I decide last Tuesday?" style queries.

---

## 6. Scale Challenges

These are out of scope for v1 but the architecture has clear seams for each:

| Challenge | Current state | Production path |
|-----------|--------------|-----------------|
| **Horizontal scale** | In-process `asyncio.Queue` pub/sub | Replace with Redis Streams or NATS JetStream; one channel per session_id |
| **Session state durability** | In-memory `_states` dict, wiped on restart | Redis with 24 h TTL; `SessionState` serialized as JSON |
| **Authentication** | None — single global namespace | Users table + JWT / OIDC; per-user project/task scoping; signed WS session IDs |
| **Tool idempotency** | Only `create_project` is idempotent (by title) | Add `idempotency_key` arg to all write tools; service-layer dedup on it |
| **Provider failover** | Build-time: first provider with a key wins | Runtime retry with backoff on same provider, then fallback; same for Deepgram/Cartesia |
| **Reminder delivery** | Stored but never fires (`services/reminders.py`) | APScheduler or dedicated worker reading `reminder_at < now`; push via WS / FCM / email |
| **Observability** | `loguru` + `print()` | OpenTelemetry spans per turn: STT duration, LLM duration, per-tool duration, TTS first-byte |
| **Spend caps** | None | Per-session token budget; kill-switch on anomalous Deepgram/Cartesia/Anthropic spend |
| **Multi-user** | Global project namespace | Per-user data isolation; CRDT or operational-transform for collaborative editing |
| **Multi-region latency** | Unoptimized | Pin Neon, Daily, Deepgram, Cartesia to same region per user (saves 100–200 ms per cross-region hop) |
| **Daily room cleanup** | Explicit `DELETE /rooms/:id` via done-callback when pipeline task exits (normal or error) | Room reuse for reconnects |
| **STT/TTS fallback** | Deepgram / Cartesia are single points of failure | Deepgram → Speechmatics / Whisper fallback; Cartesia → ElevenLabs fallback |

---

## 7. What's Intentionally Not in v1

- **Reminder delivery** — `reminder_at` is stored; no scheduler or push mechanism.
- **Authentication** — single-user; no user table; no per-user data isolation.
- **Transcript persistence** — conversation history is ephemeral.
- **Undo stack** — "actually" corrections rely on prompt-driven LLM semantics, not a compensating-transaction log.
- **`clarification.resolved` server event** — UI dismisses the clarification prompt locally; no server-side wiring back into the LLM context. The LLM continues from the user's spoken reply naturally.
- **Concurrent multi-user sessions** — `projects.title` is globally unique; two users sharing a DB would collide.

---

## 8. Loom Walkthrough Script (5–7 min)

| Time | Scene | What to say / show |
|------|-------|-------------------|
| 0:00–0:30 | Title card / blank browser | "Vox PM — voice-first PM tool for the camb.ai SSE take-home. The problem: users speak in long, messy sentences with corrections and ambiguous refs. The UI must reflect intent in real time." |
| 0:30–1:00 | UI tour (no session yet) | Show empty state (voice-facts panel, 3× faster stat, 67 hrs/year). Point out: "+ New project" is muted/secondary — voice is primary. Theme cycle button. |
| 1:00–3:00 | **Live demo — assignment example** | Say verbatim: *"Add a task to finalize the Q2 report… actually make that a project, and under it add three tasks: draft the intro, get numbers from finance, review with Sarah. The finance one is urgent, due Friday. Wait, move the review task to a new project called Q2 Review instead. And remind me about the finance task tomorrow morning."* Watch: action feed shows tool calls live, sidebar updates, task rows appear with urgency + date chips. Pause on result: show Q2 report (2 tasks, finance urgent + due Friday + reminder), Q2 Review (Review with Sarah). |
| 3:00–3:30 | **Correction demo** | Start a new sentence with "actually…" mid-way — show the LLM honoring only the final intent. Then try "wait, also add…" — show it appending, not rolling back. |
| 3:30–4:00 | **Clarification demo** | With 2+ projects present, say "delete the project" — show `ClarificationPrompt` chips appear. Speak one name — correct project deleted, UI clears. |
| 4:00–5:00 | **Architecture** | Show the ASCII diagram from §2. Walk: mic → Daily audio → Deepgram STT → Sonnet 4.6 → tool dispatch → Neon → event bus → WS → React. Key point: two separate channels (Daily for audio, custom WS for state events). Show the debug events panel with the raw WS stream. |
| 5:00–6:00 | **Three decisions** | (1) Tool-sequencing-before-speech — show what happens vs. not (fragmented audio). (2) Workspace snapshot rebuilt per tool — why correctness beats cost. (3) Alias map (P1/T3) — open the debug panel, show the snapshot text injected into the system prompt. |
| 6:00–7:00 | **Scale story + close** | Walk §6 table: Redis for pub/sub, session state to Redis, auth, provider failover at runtime, observability. "For a voice-AI company what matters most here is the latency budget — today it's 2.5–4.5 s end-to-end; biggest wins would be streaming tool results and regional pinning." Close with repo URL. |

---

## 9. Repo Map (critical files)

```
apps/
├── api/src/vox_pm/
│   ├── agent/
│   │   ├── pipeline.py        # Frame graph, tool handler, snapshot refresh
│   │   ├── prompts.py         # System prompt rules (terse, <20 lines)
│   │   ├── tools.py           # Tool schema (TOOLS_SCHEMA) + dispatch
│   │   ├── state.py           # SessionState, alias map, snapshot_text()
│   │   └── llm/factory.py     # Provider fallback chain
│   ├── events/
│   │   ├── bus.py             # asyncio.Queue pub/sub
│   │   └── ws.py              # /ws/events WebSocket gateway
│   ├── services/
│   │   ├── projects.py        # Idempotent create, reparent-on-delete
│   │   └── tasks.py           # CRUD, move, position management
│   ├── models.py              # Schema + composite index + unique constraint
│   └── db.py                  # Pool tuning, Neon SSL handling, warm-up
└── web/src/
    ├── hooks/
    │   ├── useStore.ts         # Zustand reducer, event caps (50/100)
    │   └── useEventStream.ts   # WS with activeRef reconnect guard
    └── components/
        ├── ErrorBoundary.tsx   # Render-crash fallback
        ├── TaskRow.tsx         # safeFormat date guard
        └── TaskPane.tsx        # Empty state with voice-facts panel
```

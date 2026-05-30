# Vox PM — Voice-Controlled Project Manager

Talk continuously. The agent parses intent from speech in real-time, executes PM operations (create/move/update/delete projects and tasks), and the UI updates live via WebSocket.

**Loom walkthrough (5–10 min):** https://www.loom.com/share/f62b05e4f18d474cad103d0185a48c76

---

## Docs

| File | What's in it |
|------|-------------|
| [WRITEUP.md](WRITEUP.md) | Architecture deep-dive, design decisions, voice tradeoffs, scale challenges, Loom script |
| [RUNNING.md](RUNNING.md) | Detailed local setup, env vars, DB setup |
| [TEST_CHECKLIST.md](TEST_CHECKLIST.md) | Manual regression checklist (R1–R9), all passing |
| [docs/CONTEXT.md](docs/CONTEXT.md) | Domain model, entities, business rules |
| [apps/api/src/vox_pm/agent/README.md](apps/api/src/vox_pm/agent/README.md) | Agent pipeline, tool dispatch, reference resolution |
| [apps/api/src/vox_pm/events/README.md](apps/api/src/vox_pm/events/README.md) | Event types, pub/sub architecture, WS gateway |

---

## Architecture

```
Browser mic ──WebRTC──► Daily.co ──► Pipecat pipeline (Python)
                                         │
                               Silero VAD → Deepgram STT (nova-3, interim results)
                                         │
                               Claude Sonnet 4.6 + tool calls
                                         │
                               services/  ──► Neon Postgres (direct, no pooler)
                                         │
                               asyncio event bus ──► WS /ws/events
                                         │
React + Zustand ◄──WebSocket─────────────┘
```

Two channels: **Daily WebRTC** for audio, **custom WebSocket** for all state events (transcripts, tool calls, entity CRUD, clarifications). See [WRITEUP.md](WRITEUP.md) for full design rationale.

---

## Quickstart

### Prerequisites

- Python 3.12 + [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node 22 + [pnpm](https://pnpm.io/installation)
- API keys: Deepgram, Cartesia, Daily, Anthropic (or OpenAI/Gemini)

### 1. Install

```bash
cp .env.example .env
# Fill in your API keys in .env

cd apps/api && uv sync && cd ../..
pnpm install
```

### 2. Environment variables

```bash
# Database — use direct hostname, no -pooler suffix
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/voxpm?sslmode=require

# LLM — first key found wins (anthropic → gemini → openai fallback)
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...        # optional fallback
# GOOGLE_API_KEY=AIza...       # optional fallback (Gemini)

# Voice
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
CARTESIA_VOICE_ID=a0e99841-...

# Daily.co (WebRTC rooms)
DAILY_API_KEY=...

# CORS — set to your frontend URL in production
CORS_ORIGINS=http://localhost:5173
```

Tables are created automatically on first startup. **Existing DB from a previous run:** `create_all` won't add new columns, so add the reminder-delivery column once:
```sql
ALTER TABLE tasks ADD COLUMN reminder_fired boolean NOT NULL DEFAULT false;
```
(Or just recreate the dev DB.)

### 3. Run

```bash
pnpm dev
```

- API: http://localhost:8000 (docs at /docs)
- Web: http://localhost:5173

### 4. Use

1. Open http://localhost:5173
2. Click **Start session** — grants mic access and joins a Daily room
3. Speak naturally, e.g.:

> *"Add a task to finalize the Q2 report... actually make that a project, and under it add three tasks: draft the intro, get numbers from finance, review with Sarah. The finance one is urgent, due Friday. Wait, move the review task to a new project called Q2 Review instead. And remind me about the finance task tomorrow morning."*

The UI updates in real-time as each tool call fires. Agent actions appear in the right panel.

You can also create projects manually via **+ New project** in the sidebar (voice is faster).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Pipecat 1.2+ |
| Voice | Daily.co WebRTC, Deepgram STT (nova-3), Cartesia TTS |
| LLM | Claude Sonnet 4.6 (fallback: GPT-4o, Gemini — auto-detected from env) |
| Database | Neon Postgres via SQLModel + asyncpg (direct connection, pool_size=10) |
| Real-time | FastAPI WebSocket, asyncio in-process event bus |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS v4, shadcn/ui |
| Deploy | Fly.io (API), Vercel (Web) |

---

## UI Features

- **3-pane Linear-style layout**: sidebar (projects) | main (tasks) | right (voice + activity feed)
- **Voice-first**: sidebar prompts voice use; manual create/rename/delete as fallback
- **Live transcript**: partial (italic) → final with `You` label
- **Activity feed**: every mutation logged with type, summary, timestamp — agent tool calls *and* manual UI changes (REST mutations publish the same events, so the feed doubles as multi-tab activity)
- **Reminder toast**: when a task's `reminder_at` comes due, a reminder fires over the WS and surfaces as an amber toast + action-feed entry
- **Debug panel**: toggle with `D` button in header — shows raw WS events
- **Manual actions**: checkbox to mark done, hover → delete/rename via dropdown

---

## Agent tools

| Tool | What it does |
|------|-------------|
| `create_project` | Create project (idempotent by title) |
| `update_project` | Rename project |
| `delete_project` | Delete project |
| `create_task` | Create task, optionally in a project |
| `update_task` | Update title/description/urgent/due_at/reminder_at/status |
| `delete_task` | Delete task |
| `move_task` | Move task to different project |
| `convert_task_to_project` | Delete task, create project with same title |
| `ask_clarification` | Ask user when reference is genuinely ambiguous |

All tool arguments are validated against per-tool pydantic schemas before dispatch (bad types / unknown fields / invalid status are rejected before any DB write). `create_task` is idempotent within a short window — a retried create (same title+project) after an interruption returns the existing task instead of duplicating.

---

## Deploy

### Fly.io (API)

```bash
fly auth login
fly apps create vox-pm-api
fly secrets set \
  DATABASE_URL="postgresql+asyncpg://user:pass@ep-xxx.neon.tech/voxpm?sslmode=require" \
  ANTHROPIC_API_KEY="..." \
  DEEPGRAM_API_KEY="..." \
  CARTESIA_API_KEY="..." \
  DAILY_API_KEY="..." \
  CORS_ORIGINS="https://your-vercel-domain.vercel.app"
fly deploy
```

### Vercel (Web)

```bash
cd apps/web
vercel --prod
# Set env vars: VITE_API_BASE=https://vox-pm-api.fly.dev
#               VITE_WS_BASE=wss://vox-pm-api.fly.dev
```

---

## Project structure

```
apps/
├── api/                          # FastAPI + Pipecat backend
│   └── src/vox_pm/
│       ├── agent/
│       │   ├── pipeline.py       # Pipecat frame graph (VAD→STT→LLM→TTS)
│       │   ├── prompts.py        # System prompt + snapshot injection
│       │   ├── tools.py          # Tool schema + dispatch (9 tools), arg validation + create dedupe
│       │   ├── tool_args.py      # Per-tool pydantic validation models
│       │   ├── state.py          # SessionState, alias map, reference resolution, create-dedupe cache
│       │   └── llm/factory.py    # Provider fallback (Anthropic→OpenAI→Gemini)
│       ├── events/
│       │   ├── bus.py            # asyncio pub/sub (per-session queues) + broadcast()
│       │   └── ws.py             # WebSocket gateway /ws/events
│       ├── services/
│       │   ├── projects.py       # Project CRUD (idempotent create, reparent-on-delete)
│       │   └── tasks.py          # Task CRUD, move, position management
│       ├── reminders.py          # Background poll loop — fires due reminders over WS
│       ├── models.py             # SQLModel schema + indexes
│       └── db.py                 # Async engine, pool config, Neon SSL handling
└── web/                          # React frontend
    └── src/
        ├── hooks/
        │   ├── useStore.ts        # Zustand store + WS event reducer
        │   ├── useEventStream.ts  # WebSocket client with reconnect guard
        │   └── useEventStream.test.ts  # vitest: reconnect/backoff coverage
        └── components/
            ├── Sidebar.tsx        # Project list + create/rename/delete
            ├── TaskPane.tsx       # Task list + empty state
            ├── TaskRow.tsx        # Task row with date chips + actions
            ├── ActionFeed.tsx     # Agent action feed (capped 50)
            ├── ReminderToast.tsx  # Amber toast when a reminder fires
            └── DebugPanel.tsx     # Raw WS event log (toggle with D)
```

---

## Development

```bash
pnpm test               # Python unit tests (pytest) — tools, arg validation, idempotency, reminders, events
pnpm --filter web test  # Frontend unit tests (vitest) — WS reconnect/backoff
pnpm check              # ruff + mypy + tsc + eslint
pnpm --filter web typecheck   # TypeScript only
```

---

## How the agent works

1. **Deepgram** streams interim transcripts → `transcript.partial` events shown in UI as italic text
2. On silence (300ms endpointing), final transcript triggers LLM turn
3. **LLM** receives system prompt with today's date (UTC) + full workspace snapshot (P1/T1 aliases for reference resolution)
4. LLM executes ALL required tool calls in sequence before producing any spoken response
5. Each tool: args validated against a pydantic schema → references resolved → DB write → typed WS event published → React applies as reducer (optimistic update)
6. **Cartesia TTS** plays confirmation audio after all tools complete
7. `allow_interruptions=True` — user can speak mid-TTS to correct or continue. A barge-in cancels in-flight tools, so the dispatch is `asyncio.shield`-ed (the write still commits) and the system-prompt snapshot is refreshed at the start of every turn, reconciling any tool the framework marked `CANCELLED`.

A background worker ([reminders.py](apps/api/src/vox_pm/reminders.py)) polls every 15s for tasks whose `reminder_at` has come due and fires a `reminder.fired` event over the WS (marked delivered only once a client receives it, so it survives reconnects).

**Reference resolution:** "that one" → last touched entity. "the finance one" → fuzzy title match. "first task" → T[0] in snapshot.  
**Corrections:** "actually make that a project" → `convert_task_to_project` on last touched task.  
**Ambiguity:** unresolvable ref → `ask_clarification` → purple prompt in UI → user speaks answer.

# Vox PM — Voice-Controlled Project Manager

Talk continuously. The agent parses intent from speech in real-time, executes PM operations (create/move/update projects and tasks), and the UI updates live.

See the [Loom walkthrough](#) (to be recorded).

---

## Architecture

```
Browser mic ──WebRTC──► Daily.co ──► Pipecat pipeline (Python)
                                         │
                               DeepgramSTT (interim results)
                                         │
                               LLM (Claude/GPT-4o) + tool calls
                                         │
                               services/  ──► Neon Postgres
                                         │
                               event bus ──► WS /ws/events
                                         │
React frontend ◄──WebSocket──────────────┘
```

**Key design decisions:** [ADR 0001–0004](docs/adr/)
**Domain model:** [docs/CONTEXT.md](docs/CONTEXT.md)
**Agent design:** [apps/api/src/vox_pm/agent/README.md](apps/api/src/vox_pm/agent/README.md)

---

## Quickstart

### Prerequisites

- Python 3.12 + [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node 22 + [pnpm](https://pnpm.io/installation)
- API keys: Deepgram, Cartesia, Daily, and either Anthropic or OpenAI

### 1. Install

```bash
cp .env.example .env
# Fill in your API keys in .env

cd apps/api && uv sync && cd ../..
pnpm install
```

### 2. Database

Use your Neon Postgres URL in `.env`:
```
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.neon.tech/voxpm?sslmode=require
```

Run migrations:
```bash
pnpm db:migrate
```

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

The UI updates in real-time as each tool call fires.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Pipecat |
| Voice | Daily.co WebRTC, Deepgram STT, Cartesia TTS |
| LLM | Claude Sonnet 4.6 (or GPT-4o, auto-detected from env) |
| Database | Neon Postgres via SQLModel + asyncpg |
| Real-time | FastAPI WebSocket, asyncio event bus |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Deploy | Fly.io (API), Vercel (Web) |

---

## Deploy

### Fly.io (API)

```bash
fly auth login
fly apps create vox-pm-api
fly secrets set \
  DATABASE_URL="..." \
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
# Set env vars: VITE_API_BASE, VITE_WS_BASE
```

---

## Development

```bash
pnpm test          # Python unit tests
pnpm check         # ruff + mypy + tsc + eslint
pnpm db:revision   # "describe migration" — generates Alembic migration
```

---

## How the agent works

1. **Deepgram** streams interim transcripts → `transcript.partial` events show in UI
2. On silence (endpointing), final transcript triggers LLM turn
3. **LLM** receives system prompt with full workspace state snapshot (for "the first task", "that one" resolution)
4. LLM emits tool calls (often multiple per turn) — `create_project`, `create_task`, `move_task`, etc.
5. Each tool call: executes against Postgres, publishes typed event to bus, WS pushes to frontend
6. **React** applies events as reducers — projects/tasks update immediately
7. LLM TTS response plays back confirmation audio (Cartesia)

**Correction handling:** "actually make that a project" → LLM calls `convert_task_to_project` on the last created task. System prompt includes this as an explicit example pattern.

**Ambiguity:** If LLM cannot resolve a reference, it calls `ask_clarification` → purple prompt in UI, user speaks the answer.

# Running Vox PM

## API Keys needed

| Key | Where to get |
|-----|-------------|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `DEEPGRAM_API_KEY` | console.deepgram.com |
| `CARTESIA_API_KEY` | play.cartesia.ai |
| `DAILY_API_KEY` | dashboard.daily.co |
| `DATABASE_URL` | Neon console → Connection string (use **direct** hostname, not pooler) |

## 1. Setup

```bash
cp .env.example .env
# fill in keys above

cd apps/api && uv sync && cd ../..
pnpm install
```

## 2. Run

```bash
pnpm dev
```

Tables are auto-created on first startup. If you have an existing DB from a previous run, recreate it or run:
```sql
ALTER TABLE tasks ADD CONSTRAINT uq_tasks_project_position UNIQUE (project_id, position);
ALTER TABLE tasks ADD COLUMN reminder_fired boolean NOT NULL DEFAULT false;
```
(Schema changes in `models.py` — the unique constraint and the `reminder_fired` column — won't apply to existing tables via `create_all`.)

- API → http://localhost:8000
- Swagger docs → http://localhost:8000/docs
- Web → http://localhost:5173

## 3. Tests

```bash
pnpm test               # backend (pytest): tools, arg validation, idempotency, reminders, events
pnpm --filter web test  # frontend (vitest): WS reconnect/backoff
```

## 4. Build check

```bash
pnpm --filter web build
pnpm --filter web typecheck
```

## Env file reference

```env
# Neon Postgres — use DIRECT connection (no -pooler in hostname)
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xxx.us-east-1.aws.neon.tech/voxpm?sslmode=require

# LLM — first one with a valid key wins (priority order configurable via LLM_PROVIDERS)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
# LLM_PROVIDERS=anthropic,gemini,openai   # default order

# Voice pipeline
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
CARTESIA_VOICE_ID=a0e99841-438c-4a64-b679-ae501e7d6091   # change if wanted

DAILY_API_KEY=...

ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
```

## Debug mode

Append `?debug=1` to the URL, or click the **D** button in the header to toggle the debug events panel (shows raw WebSocket events).

## Performance notes

- DB pool: `pool_size=10, max_overflow=5` — direct Neon connection, no PgBouncer overhead
- Warm-up ping fires at startup so the first tool call is fast
- Neon free tier suspends after 5 min idle; restart API before demo to warm the pool

## Deploy

```bash
# API → Fly.io
fly auth login
fly apps create vox-pm-api
fly secrets set \
  DATABASE_URL="postgresql+asyncpg://..." \
  ANTHROPIC_API_KEY="..." \
  DEEPGRAM_API_KEY="..." \
  CARTESIA_API_KEY="..." \
  DAILY_API_KEY="..." \
  CORS_ORIGINS="https://<vercel-domain>"
fly deploy

# Web → Vercel
cd apps/web
vercel --prod
# Set env: VITE_API_BASE=https://vox-pm-api.fly.dev
#          VITE_WS_BASE=wss://vox-pm-api.fly.dev
```

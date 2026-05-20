# Events Module

In-process pub/sub (asyncio) + WebSocket gateway.

## Event types

| type | data |
|------|------|
| `transcript.partial` | `{text}` |
| `transcript.final` | `{text}` |
| `agent.thinking` | `{}` |
| `agent.error` | `{message}` |
| `tool.started` | `{name, arguments}` |
| `tool.completed` | `{name, result, duration_ms}` |
| `tool.failed` | `{name, error, duration_ms}` |
| `project.created` | `{project: ProjectRead}` |
| `project.updated` | `{project: ProjectRead}` |
| `project.deleted` | `{id}` |
| `task.created` | `{task: TaskRead}` |
| `task.updated` | `{task: TaskRead, changed_fields: []}` |
| `task.deleted` | `{id}` |
| `task.moved` | `{task: TaskRead, from_project_id, to_project_id}` |
| `clarification.ask` | `{question, candidates: []}` |
| `clarification.resolved` | `{}` |

## Architecture

`bus.py` — `dict[session_id → list[asyncio.Queue]]`. `publish(session_id, type, data)` enqueues to all subscribers for that session. Full queues are pruned (dead consumer cleanup).

`ws.py` — FastAPI WebSocket route at `/ws/events?session_id=<id>`. Subscribes a queue on connect, streams events as JSON, unsubscribes on disconnect. Sends `{"type":"ping"}` every 30s to keep connection alive.

## Frontend connection

`useEventStream.ts` — connects immediately after receiving `session_id` from `/api/voice/session`. Uses an `activeRef` flag to prevent reconnect loops when session ends (guards against server-closes-before-React-cleanup race condition). Auto-reconnects with 2s delay if connection drops while session is still active.

`useStore.applyEvent()` — Zustand reducer that handles all event types. Project/task create events are idempotent (dedupe by id). Actions array capped at 50 entries.

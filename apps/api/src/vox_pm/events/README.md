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
| `reminder.fired` | `{task: TaskRead}` |
| `clarification.ask` | `{question, candidates: []}` |
| `clarification.resolved` | `{}` |

## Architecture

`bus.py` — `dict[session_id → list[asyncio.Queue]]`. `publish(session_id, ...)` delivers **only to subscribers registered under that session_id**. On `QueueFull`, drops the oldest event from the queue and inserts the new one (preserves the subscriber; loses one old event) rather than permanently evicting the slow subscriber.

All three event sources use the same `session_id` key (the frontend `clientId`):
- REST routers read it from the `X-Client-Id` request header.
- The voice pipeline receives it from the session-creation request body and uses it throughout the pipeline lifetime.
- WS clients subscribe with `?session_id=<clientId>`.

`broadcast(event_type, data)` — fans an event out to **every** connected session (returns the count delivered to). Used only by the reminder worker (`reminders.py`), which has no single owning session in the single-user model; the count lets the worker mark a reminder `fired` only once a client actually received it.

`ws.py` — FastAPI WebSocket route at `/ws/events?session_id=<id>`. Subscribes a queue on connect, streams events as JSON, unsubscribes on disconnect. Sends `{"type":"ping"}` every 30s to keep the connection alive. Unexpected non-disconnect exceptions are logged (not swallowed).

## Frontend connection

`useEventStream.ts` — connects on component mount using a **stable client ID** from `localStorage` (generated once with `crypto.randomUUID()`, persisted across page loads). The connection is not gated on an active voice session, so manual CRUD events (rename, delete, toggle) are visible in the UI at all times.

`api.ts` exports the same `clientId` constant and attaches it as an `X-Client-Id` header on every REST request. This ensures REST-originated mutations (`project.created`, `task.deleted`, etc.) are routed to the same subscriber queue as voice events.

Reconnect uses **exponential backoff** (1 s → 2 s → 4 s … capped at 30 s, with ±0.5 s jitter). On successful `onopen`, backoff resets and `loadInitialState` is called to reconcile any state that drifted during the disconnection window (merges by id — server copy wins for known entities). A pending reconnect timer is always cancelled before opening a new connection to prevent duplicate sockets.

`useStore.applyEvent()` — Zustand reducer that handles all event types. Project/task create events are idempotent (dedupe by id). `loadInitialState` merges server state with local state by id (not a full overwrite) to avoid wiping in-flight live events. Actions array capped at 50 entries.

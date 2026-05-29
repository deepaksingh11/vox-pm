# ADR 0003: In-process asyncio event bus + dedicated WS endpoint

**Status:** Accepted

**Context:** Real-time UI updates need to flow from tool calls (deep inside the Pipecat pipeline task) to the React frontend.

**Decision:** Simple `asyncio.Queue` per WS subscriber. Services call `publish(session_id, event_type, data)`. WS endpoint `/ws/events?session_id=...` dequeues and sends. `publish()` **broadcasts to all subscribers** (not filtered by session_id) because the workspace is global — per-session routing caused REST-originated mutations to publish to `"default"` while WS clients subscribed to voice-session UUIDs, making manual CRUD invisible in the live UI.

The frontend generates a **stable client ID** (`crypto.randomUUID()`, persisted in `localStorage`) and connects on mount — not gated on an active voice session. Manual edits (rename, delete, toggle) are live regardless of whether a voice session exists.

**Alternatives rejected:**
- RTVI `send_client_data` — ties event format to RTVI protocol; harder to add multiple consumers
- Redis pub/sub — overkill for single-process demo; adds infra dependency
- SSE — WebSocket better for bi-directional (future: client → server clarification answers)

**Consequences:**
- Events in the bus queue during a WS disconnect are not replayed on reconnect; `loadInitialState` (called on reconnect) reconciles entity state via REST, so the UI recovers to correct state even if individual events were missed.
- On `QueueFull`, the oldest event in the queue is dropped (not the subscriber) — the subscriber stays alive and continues receiving future events, at the cost of one missed old event.
- Multiple browser tabs each get their own queue; all receive all broadcasts. UI is idempotent via entity ID upsert, so duplicate delivery is safe.

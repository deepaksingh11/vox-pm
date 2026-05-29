# ADR 0003: In-process asyncio event bus + dedicated WS endpoint

**Status:** Accepted

**Context:** Real-time UI updates need to flow from tool calls (deep inside the Pipecat pipeline task) to the React frontend. Three independently-keyed id-spaces existed: REST routers published to `"default"`, the voice pipeline published to a server-generated UUID, and WS clients subscribed using a stable `clientId` from `localStorage`. These three buckets never aligned, so earlier versions used a global broadcast workaround.

**Decision:** Use `asyncio.Queue` per WS subscriber, keyed by `session_id`. `publish(session_id, event_type, data)` delivers only to `_subscribers.get(session_id, [])` — no cross-subscriber fan-out.

To make the three id-spaces align on a single key:
- The frontend generates a **stable client ID** (`crypto.randomUUID()`, persisted in `localStorage`) and passes it in two ways: as `X-Client-Id` header on every REST request, and as `client_id` in the voice-session creation body.
- REST routers read `X-Client-Id` and pass it as `session_id` to all service-layer `publish()` calls.
- The voice router uses the client-supplied `client_id` as the pipeline's `session_id` (and returns it as the `session_id` in the response so the frontend can call `DELETE /session/{id}`).
- WS clients connect with `?session_id=<clientId>` — same value.

All three channels now publish and subscribe under the same key, so every event (manual CRUD from REST, voice tool calls, transcripts) arrives at the correct subscriber.

**Alternatives rejected:**
- RTVI `send_client_data` — ties event format to RTVI protocol; harder to add multiple consumers
- Redis pub/sub — overkill for single-process demo; adds infra dependency
- SSE — WebSocket better for bi-directional (future: client → server clarification answers)

**Consequences:**
- Events in the bus queue during a WS disconnect are not replayed on reconnect; `loadInitialState` (called on reconnect) reconciles entity state via REST, so the UI recovers to correct state even if individual events were missed.
- On `QueueFull`, the oldest event in the queue is dropped (not the subscriber) — the subscriber stays alive and continues receiving future events, at the cost of one missed old event.
- Multiple browser tabs sharing the same `localStorage` get the same `clientId` and therefore the same queue; all tabs receive the same events. UI is idempotent via entity ID upsert, so duplicate delivery is safe.
- No cross-client event leakage: a second browser (different `localStorage`) gets its own queue and only sees its own events.

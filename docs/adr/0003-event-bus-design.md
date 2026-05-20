# ADR 0003: In-process asyncio event bus + dedicated WS endpoint

**Status:** Accepted

**Context:** Real-time UI updates need to flow from tool calls (deep inside the Pipecat pipeline task) to the React frontend.

**Decision:** Simple `asyncio.Queue` per WS subscriber, keyed by `session_id`. Services call `publish(session_id, event_type, data)`. WS endpoint `/ws/events?session_id=...` dequeues and sends.

**Alternatives rejected:**
- RTVI `send_client_data` — ties event format to RTVI protocol; harder to add multiple consumers
- Redis pub/sub — overkill for single-process demo; adds infra dependency
- SSE — WebSocket better for bi-directional (future: client → server clarification answers)

**Consequences:**
- Events are lost if WS disconnects during tool execution (unlikely for demo; reconnect logic in `useEventStream.ts` recovers quickly)
- Multiple browser tabs to same session each get their own queue = duplicate events per tab (acceptable; UI is idempotent via entity ID replace)

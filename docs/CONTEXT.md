# Domain Context

## Entities

**Project** — a named bucket for tasks. Created, renamed, deleted by voice or via sidebar dropdown. Referenced by title in speech ("the Q2 report project").

**Task** — a unit of work. Has title, optional project, urgency flag, due date, reminder time, status (open/done), position. Position enables ordinal references ("the first task").

**Session** — one voice conversation. The browser's stable `client_id` (a UUID persisted in `localStorage`) serves as the single routing key for all three event channels: REST requests carry it as the `X-Client-Id` header, the voice session creation body sends it as `client_id`, and the WS connection uses it as `session_id`. This means REST mutations, voice pipeline events, and the WS subscription all share the same queue. In-memory per process; stateless across restarts. Session state (`SessionState`, alias map) is cleaned up in a `finally` block when the pipeline exits. Two termination modes: (1) **intentional** — user clicks "End session" → `DELETE /api/voice/session/{client_id}` → pipeline cancelled, Daily room deleted; (2) **unintentional** (network blip) — WS disconnects, frontend reconnects with exponential backoff (1 s→30 s cap), then calls `loadInitialState` to reconcile entity state from REST (merge by id, server copy wins). Events queued in the bus during the disconnection window are not replayed, but DB state is the source of truth — `loadInitialState` on reconnect recovers it.

**Agent** — the Pipecat pipeline's LLM component (Claude Sonnet 4.6). Receives finalized transcripts, emits tool calls against the service layer, speaks confirmation via Cartesia TTS.

**Action** — a UI-side record of something the agent did. Built from WS events in the Zustand store. Displayed in the ActionFeed (right panel), capped at 50, in-memory only (not persisted). Intentionally ephemeral — session artifact only; not part of the persistent domain. On reload, feed is blank; task/project state restores from REST.

**Reference** — a deictic pointer in speech: "that one", "it", "the first task", "the finance one". Resolved by `SessionState.recent` and the workspace snapshot injected into the system prompt. `ask_clarification` fires when: (1) ref is ambiguous (multiple matches) and action is irreversible; (2) user says "delete the project" without naming one — always confirm, even with a single project; (3) user says "add a task" with no active project context and multiple projects exist. If user ignores the prompt and gives a new command, clarification is discarded (cleared on first `tool.started` event). If user speaks the answer, LLM resolves it from the next transcript turn — no server-side `clarification.resolved` wiring in v1.

## Domain Rules

- A task can exist without a project (orphaned/unassigned). Created when a project is deleted — tasks are reparented to `project_id=null` rather than cascade-deleted. Orphans are DB-only artifacts: excluded from workspace snapshot (LLM can't see or act on them), not rendered in UI (no unassigned view). Inbox concept removed.
- Moving a task to a project updates its `project_id`; position = end of target list via `MAX(position)+1`. Position is append-only — no reordering in v1. Ordinal refs ("the first task") resolve by insertion order. A `UniqueConstraint("project_id", "position")` prevents concurrent creates from colliding (retry on `IntegrityError`). Note: PostgreSQL treats `(NULL, n)` as distinct from other `(NULL, n)` rows in unique constraints, so the constraint applies only to project-scoped tasks.
- Task status: `open` (default) | `in_progress` | `blocked` | `cancelled` | `done`. Agent can set any via `update_task`. UI checkbox toggles between done↔open (non-done → done; done → open). Status badges shown inline for `in_progress` (blue), `blocked` (orange), `cancelled` (muted).
- Urgency: `urgent=true` → red badge in UI. Triggered by "urgent", "ASAP", "high priority".
- Due dates and reminders stored as `TIMESTAMP WITHOUT TIME ZONE` (UTC, tzinfo stripped before insert).
- Reminders fire via a background poll loop (`reminders.py`, 15 s) that broadcasts `reminder.fired` over the WS when `reminder_at` comes due. `reminder_fired` flag guarantees once-only delivery and is **deliver-then-mark** — only set once a client received it, so a reminder due while no client is connected fires on reconnect rather than being lost. Setting/changing `reminder_at` re-arms the flag. Rendered as a bell chip in TaskRow + an amber `ReminderToast` when it fires. Single-user: broadcast to all sessions (no per-user routing in v1).
- "Convert task to project" = atomic single-commit operation: project created (flush → get id), task deleted, single commit. Failure before commit leaves the task intact. LLM strips leading action verbs from the title using judgment (e.g. "Finalize the Q2 report" → "Q2 report") — no finite verb list.
- `create_project` is idempotent by title — returns existing project if title matches (handles LLM retry after interrupted tool call). On TOCTOU race (two concurrent creates with same title), catches `IntegrityError` on commit, rolls back, re-fetches the winner rather than returning a 500.
- `create_task` is idempotent within a short window — same title+project within 8 s (per session) returns the existing task (`deduped: true`) instead of inserting a duplicate. Targets the interruption/retry case; tasks legitimately repeat titles, so this is a time-boxed dedupe, not a unique constraint. Cache lives in `SessionState`.
- LLM tool arguments are validated against per-tool pydantic models (`agent/tool_args.py`, `extra="forbid"`) at the top of `dispatch_tool`, before reference resolution or any DB write. Wrong types, invalid `status` enums, and unknown fields return `{"ok": False, "error": ...}` — the LLM gets a readable error and no malformed row reaches the DB. Dates remain strings here (parsed/normalized by `_parse_dt`).
- LLM receives today's date (UTC) in system prompt for correct relative date resolution ("Friday", "tomorrow morning").
- Titles stored and displayed in sentence case (first word capitalized only). Enforced via system prompt rule.

## Key Boundaries

- REST API (`/api/projects`, `/api/tasks`) = initial load + manual CRUD from UI. Agent writes via tool calls only (not REST).
- `selectedProjectId` (UI) and `SessionState.current_project_id` (agent) are deliberately independent. UI selection is a visual concern; agent context is a voice conversation concern. The agent's context wins for ambiguous voice commands ("add a task" without a project name). `current_project_id` is updated by `touch()` on any project/task interaction; cleared immediately when that project is deleted (prevents FK violation on next create_task).
- WebSocket (`/ws/events?session_id=`) = server-push only. Frontend never sends on WS.
- Event bus = in-process `asyncio.Queue` per subscriber, keyed by `session_id` (the frontend `clientId`). Delivery is per-session via `publish()`. One exception: `broadcast()` fans out to every connected session and is used only by the reminder worker, which has no single owning session in the current single-user model. No external broker. Events lost on process restart.
- Frontend Zustand store = optimistic mutations for manual actions + WS event reducer for agent actions. Both paths are idempotent (dedupe by id). Optimistic mutations (toggle, delete, rename) capture previous state and roll back on API failure — no diverged UI state on network error.
- No RTVI — Daily.co WebRTC for audio only; all state events on the custom WS bus.

## System Prompt Design

Injected per session start and refreshed after each tool call:
- Today's date (UTC) for relative date resolution
- Full workspace snapshot (`P1 "title" / T1 "title" !` format) for entity reference
- Last-touched entity marker (`^P` / `^T`) for "it"/"that" resolution
- Rules: sentence-case titles, tool sequencing (all tools before speech), urgency flags, clarification threshold

## UI Layout

Three-pane Linear-style:
- **Left sidebar**: project navigation, `+ New project` (muted, voice-first tooltip)
- **Main pane**: task list for selected project, empty states push voice usage
- **Right panel**: voice control (Start/End session, mute), live transcript, clarification prompt, agent actions feed, debug events panel (toggle with `D` header button)

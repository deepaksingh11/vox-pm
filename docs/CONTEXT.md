# Domain Context

## Entities

**Project** — a named bucket for tasks. Created, renamed, deleted by voice or via sidebar dropdown. Referenced by title in speech ("the Q2 report project").

**Task** — a unit of work. Has title, optional project, urgency flag, due date, reminder time, status (open/done), position. Position enables ordinal references ("the first task").

**Session** — one voice conversation. `session_id` shared between Pipecat pipeline (backend) and WS event stream (frontend). In-memory per process; stateless across restarts. Two termination modes: (1) **intentional** — user clicks "End session" → `DELETE /api/voice/session/{id}` → pipeline cancelled, no resume; (2) **unintentional** (network blip) — WS disconnects but pipeline keeps running, frontend reconnects within 2s to same `session_id` and re-subscribes. Events published during the reconnect window are lost.

**Agent** — the Pipecat pipeline's LLM component (Claude Sonnet 4.6). Receives finalized transcripts, emits tool calls against the service layer, speaks confirmation via Cartesia TTS.

**Action** — a UI-side record of something the agent did. Built from WS events in the Zustand store. Displayed in the ActionFeed (right panel), capped at 50, in-memory only (not persisted). Intentionally ephemeral — session artifact only; not part of the persistent domain. On reload, feed is blank; task/project state restores from REST.

**Reference** — a deictic pointer in speech: "that one", "it", "the first task", "the finance one". Resolved by `SessionState.recent` and the workspace snapshot injected into the system prompt. `ask_clarification` fires when: (1) ref is ambiguous (multiple matches) and action is irreversible; (2) user says "delete the project" without naming one — always confirm, even with a single project; (3) user says "add a task" with no active project context and multiple projects exist. If user ignores the prompt and gives a new command, clarification is discarded (cleared on first `tool.started` event). If user speaks the answer, LLM resolves it from the next transcript turn — no server-side `clarification.resolved` wiring in v1.

## Domain Rules

- A task can exist without a project (orphaned/unassigned). Created when a project is deleted — tasks are reparented to `project_id=null` rather than cascade-deleted. Orphans are DB-only artifacts: excluded from workspace snapshot (LLM can't see or act on them), not rendered in UI (no unassigned view). Inbox concept removed.
- Moving a task to a project updates its `project_id`; position = end of target list. Position is append-only — no reordering in v1. Ordinal refs ("the first task") resolve by insertion order.
- Task status: `open` (default) | `in_progress` | `blocked` | `cancelled` | `done`. Agent can set any via `update_task`. UI checkbox toggles between done↔open (non-done → done; done → open). Status badges shown inline for `in_progress` (blue), `blocked` (orange), `cancelled` (muted).
- Urgency: `urgent=true` → red badge in UI. Triggered by "urgent", "ASAP", "high priority".
- Due dates and reminders stored as `TIMESTAMP WITHOUT TIME ZONE` (UTC, tzinfo stripped before insert).
- Reminders stored only — no delivery mechanism in v1. Rendered as a bell chip in TaskRow UI. Future: worker polling `reminder_at < now` to push via WS/email.
- "Convert task to project" = `delete_task` + `create_project` with same title (one tool call). LLM strips leading action verbs from the title using judgment (e.g. "Finalize the Q2 report" → "Q2 report") — no finite verb list.
- `create_project` is idempotent by title — returns existing project if title matches (handles LLM retry after interrupted tool call).
- LLM receives today's date (UTC) in system prompt for correct relative date resolution ("Friday", "tomorrow morning").
- Titles stored and displayed in sentence case (first word capitalized only). Enforced via system prompt rule.

## Key Boundaries

- REST API (`/api/projects`, `/api/tasks`) = initial load + manual CRUD from UI. Agent writes via tool calls only (not REST).
- `selectedProjectId` (UI) and `SessionState.current_project_id` (agent) are deliberately independent. UI selection is a visual concern; agent context is a voice conversation concern. The agent's context wins for ambiguous voice commands ("add a task" without a project name). `current_project_id` is updated by `touch()` on any project/task interaction; cleared immediately when that project is deleted (prevents FK violation on next create_task).
- WebSocket (`/ws/events?session_id=`) = server-push only. Frontend never sends on WS.
- Event bus = in-process `asyncio.Queue` per subscriber. No external broker. Events lost on process restart.
- Frontend Zustand store = optimistic mutations for manual actions + WS event reducer for agent actions. Both paths are idempotent (dedupe by id).
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

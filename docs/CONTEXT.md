# Domain Context

## Entities

**Project** — a named bucket for tasks. Created, renamed, deleted by voice or via sidebar dropdown. Referenced by title in speech ("the Q2 report project").

**Task** — a unit of work. Has title, optional project, urgency flag, due date, reminder time, status (open/done), position. Position enables ordinal references ("the first task").

**Session** — one voice conversation. `session_id` shared between Pipecat pipeline (backend) and WS event stream (frontend). In-memory per process; stateless across restarts.

**Agent** — the Pipecat pipeline's LLM component (Claude Sonnet 4.6). Receives finalized transcripts, emits tool calls against the service layer, speaks confirmation via Cartesia TTS.

**Action** — a UI-side record of something the agent did. Built from WS events in the Zustand store. Displayed in the ActionFeed (right panel), capped at 50, in-memory only (not persisted).

**Reference** — a deictic pointer in speech: "that one", "it", "the first task", "the finance one". Resolved by `SessionState.recent` and the workspace snapshot injected into the system prompt.

## Domain Rules

- A task can exist without a project (orphaned/unassigned). Inbox concept removed from UI — orphan tasks are unreachable via sidebar but exist in DB.
- Moving a task to a project updates its `project_id`; position = end of target list.
- Urgency: `urgent=true` → red badge in UI. Triggered by "urgent", "ASAP", "high priority".
- Due dates and reminders stored as `TIMESTAMP WITHOUT TIME ZONE` (UTC, tzinfo stripped before insert).
- Reminders stored only — no delivery mechanism in v1.
- "Convert task to project" = `delete_task` + `create_project` with same title (one tool call).
- `create_project` is idempotent by title — returns existing project if title matches (handles LLM retry after interrupted tool call).
- LLM receives today's date (UTC) in system prompt for correct relative date resolution ("Friday", "tomorrow morning").
- Titles stored and displayed in sentence case (first word capitalized only). Enforced via system prompt rule.

## Key Boundaries

- REST API (`/api/projects`, `/api/tasks`) = initial load + manual CRUD from UI. Agent writes via tool calls only (not REST).
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

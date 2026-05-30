# Vox PM — Regression Test Checklist

## Pre-flight

- [x] `pnpm dev` running — both api + web, no port conflicts
- [x] DB reachable (Neon), projects + tasks tables present
- [x] Mic + speakers working; browser mic permission granted
- [x] Clean DB or note existing state (no stale data polluting snapshot)
- [x] `http://localhost:5173` loads, no console errors
- [x] Network tab — `/ws` WebSocket connects on session start
- [x] Open with `?debug=1` to expose Debug events panel
- [x] Browser zoom 100%, dark mode on

---

## R1 — Voice input via Pipecat

- [x] Click `Start session` → status changes to "Connecting…" then "End session"; bar visualizer animates
- [x] Speak any phrase → live transcript shows partial (italic) then final text
- [x] Click mute → speak → no transcript; unmute → transcript resumes
- [x] End session → pipeline shuts down cleanly, no `CancelledError` in API logs

## R2 — Real-time UI updates

- [x] Say *"create a project called Test"* → sidebar entry appears before TTS finishes
- [x] Say *"add a task to Test called foo"* → task row appears in main pane within ~1s
- [x] DevTools WS frames show `project.created`, `task.created` events with payload
- [x] Refresh page mid-session → projects + tasks restore from DB

## R3 — CRUD + move + urgency + due dates

- [x] *"Create a project called Sprint 1"* → project appears in sidebar
- [x] *"Add tasks A, B, C to Sprint 1"* → 3 task rows listed
- [x] *"Mark task A urgent"* → red `urgent` badge on A
- [x] *"Task B is due Friday"* → calendar chip on B with correct date
- [x] *"Remind me about task C tomorrow morning"* → bell chip with tomorrow 09:00
- [x] *"Rename Sprint 1 to Sprint One"* → sidebar + main header both update
- [x] *"Delete task A"* → row vanishes; confirmed gone in DB
- [x] *"Create a project called Sprint 2"* → new project in sidebar
- [x] *"Move task B to Sprint 2"* → B moves; Sprint 1 count drops, Sprint 2 count rises
- [x] *"Delete Sprint 2"* → project gone from sidebar; selectedProjectId cleared

## R4 — Clear visual feedback for every action

- [x] Live transcript shows partial (italic) → final (`You` label) flow
- [x] Action feed shows `Tool calling…` → `Tool completed` → entity event (e.g. `Project created`) in order
- [x] Action feed labels all follow `[Noun] [verb-past]` pattern — no raw `tool.started` strings visible
- [x] DB state matches UI state after every utterance
- [x] Force a tool error (e.g. ambiguous delete) → `Tool failed` appears with red dot + error summary

## R5 — Corrections, ambiguous refs, interleaved content (assignment example)

Say this in one continuous breath:

> *"Add a task to finalize the Q2 report... actually make that a project, and under it add three tasks: draft the intro, get numbers from finance, review with Sarah. The finance one is urgent, due Friday. Wait, move the review task to a new project called Q2 Review instead. And remind me about the finance task tomorrow morning."*

Expected end state:

| Check | What |
|-------|------|
| - [x] | Project **Q2 report** exists (task converted to project) |
| - [x] | Project **Q2 Review** exists (created mid-utterance) |
| - [x] | **Q2 report** has tasks: `Draft the intro`, `Get numbers from finance` |
| - [x] | Finance task: `urgent` badge + due-Friday chip |
| - [x] | Finance task: reminder bell chip for tomorrow 09:00 |
| - [x] | **Q2 Review** has task: `Review with Sarah` |
| - [x] | No orphan "finalize the Q2 report" task left behind |
| - [x] | No duplicate projects or tasks |
| - [x] | All titles are sentence case (`Draft the intro`, not `draft the intro`) |

## R6 — Bonus: clarification when ambiguous

- [x] With 2+ projects, say *"delete the project"* → `ClarificationPrompt` shows with candidate chips
- [x] Reply with correct project name → right project deleted, clarification UI clears
- [x] With only 1 project: same phrasing → no clarification, direct delete

## R7 — Bonus: interruption handling

- [x] Agent mid-TTS reply → start speaking → TTS cuts off, new utterance processed
- [x] After interruption-cancel: no duplicate project/task created (idempotent create)
- [ ] Barge-in mid-create: say "create a project Personal stuff" and immediately keep talking ("and add a task…") → the project **still persists** (sidebar + DB), follow-up resolves against it, no FK violation, no phantom clarification candidate (shield + per-turn reconcile)

## R8 — Manual fallback

- [x] Click `+ New project` → type name → Enter → project created and auto-selected
- [x] Esc or click-away on input → cancels, no project created
- [x] Hover `+ New project` → tooltip reads *"Voice is faster — try saying 'create a project called…'"*
- [x] Click task checkbox → strikethrough; persists after page refresh
- [x] Hover task → ⋯ → `Delete` → task gone
- [x] Hover project → ⋯ → `Rename` → dialog opens, save updates sidebar + header
- [x] Hover project → ⋯ → `Delete` → native confirm → project gone, main pane clears
- [x] Theme button cycles Light → System → Dark → Light; icon updates each click

## R9 — Text consistency

- [x] New AI-created titles are sentence case (`Email infra`, not `email infra`)
- [x] Existing DB titles capitalized (run the SQL fix if not done yet)
- [x] LiveTranscript label says `You` (capital Y)
- [x] ActionFeed labels: `Tool calling…`, `Tool completed`, `Project created`, etc. — consistent casing
- [x] Dropdown items: `Rename` / `Delete` single-word, consistent across sidebar + task rows
- [x] Section headers `PROJECTS` and `ACTIVITY FEED` uppercase via CSS

---

## R10 — Fix regression checks

### Alias stability (C1/C2)
- [ ] Create 3 tasks in a project (T1, T2, T3 assigned). Delete T1. Say "mark T3 done" — confirm T3 (review task) is marked, not a different task
- [ ] Say a made-up alias ("update T99") → agent responds with "unknown reference" error, no silent no-op

### Event routing without voice session (C3/C4)
- [ ] Without starting a voice session: rename a project via sidebar → sidebar updates immediately (no reload)
- [ ] Toggle a task done → checkbox updates; if API fails, it reverts
- [ ] Open second browser tab → manual changes in one tab appear in the other

### Nullable field clearing (H1)
- [ ] Add a due date to a task. Say "remove the due date" → date chip disappears from task row, DB `due_at` is null
- [ ] Add a reminder. Say "clear the reminder" → bell chip gone

### Position uniqueness (H2)
- [ ] Say "add 5 tasks quickly: A B C D E" — all 5 appear with unique positions, correct order

### Atomic convert (H4)
- [ ] Simulate project title collision: create project "Alpha", then say "make the Alpha task a project" → if title conflicts, task survives unchanged (no data loss)

### Reconnect resync (H7/H8)
- [ ] During active session: disconnect network for 5s, reconnect → UI reconciles with DB state, no duplicate or missing items
- [ ] Backoff visible: open DevTools WS, force-close, verify reconnect intervals grow (not fixed 2s)

### agentThinking auto-clear (M4)
- [ ] Ask a question that gets a voice-only reply (no tool call, e.g. "what's on my list?") → task pane unfreezes within 12 seconds without any tool event

### Reminder delivery (#1)
- [ ] Set a near-future reminder (e.g. add a task then PATCH `reminder_at` to ~30s out via `/docs`, or say "remind me about X in one minute"). Keep the tab open → within the due time + ≤15s an amber **ReminderToast** appears + an `⏰ Reminder` entry lands in the action feed; DevTools WS shows a `reminder.fired` frame.
- [ ] Fires exactly once — toast doesn't re-appear on the next poll tick.
- [ ] Close the tab before a reminder is due, reopen after → reminder still fires on reconnect (deliver-then-mark, not lost).

### Task creation idempotency (#3)
- [ ] Trigger the same `create_task` twice within a few seconds (e.g. interrupt mid-confirmation and restate "add a task called foo") → only one task row; no duplicate.

### Tool-argument validation (#2)
- [ ] (Backend) `pnpm test` covers it: malformed args (bad type, invalid status, unknown field) are rejected with no DB write. No user-facing UI path.

## Bug log

<!--
[R#.##] Short description
  Steps:
  Expected:
  Actual:
  Severity: blocker | major | minor
-->

---

## Exit criteria

- All R1–R5 pass → green for video recording + deploy
- R6, R7 pass or have a noted known-issue acceptable for Loom
- R8, R9 pass
- Final clean-DB run to mirror evaluator first-run experience

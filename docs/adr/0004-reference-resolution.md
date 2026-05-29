# ADR 0004: LLM-based reference resolution with workspace snapshot

**Status:** Accepted

**Context:** Voice commands use deictic references: "that one", "the first task", "the finance one". Must resolve to entity IDs.

**Decision:** Inject the full workspace state (all projects + tasks with short aliases, titles, urgency flags, due dates) as a structured text block in the system prompt, refreshed after every tool call. The LLM resolves references itself using this snapshot.

**Aliases are stable for the entire session.** `P1`/`T3` are assigned once when an entity first appears in a snapshot and never change — even if the entity is deleted or other entities are added. A new entity always gets the next unused counter. This prevents the "renumber shift" bug where deleting the first project made `P1` point to a different entity the LLM had already committed to in its context.

**Unknown alias validation:** `resolve_id()` returns `None` for alias-shaped strings (`P\d+`/`T\d+`) not in the session map. `dispatch_tool` treats this as an error and returns `{"ok": False, "error": "unknown reference ..."}` rather than passing the bogus string to the DB. This catches hallucinated aliases before they reach the service layer.

**Alternatives rejected:**
- Dedicated resolver with regex/fuzzy-match — brittle, can't handle "that thing I just created"
- Embedding search over entity titles — overkill for small workspaces; latency cost

**`SessionState.recent`** tracks the rolling window of recently touched entities. The snapshot surfaces the "last touched" entity, which the LLM can use for "it" / "that one".

**Position field** on `Task` enables ordinal references: T1 is always the first task added to a project (by `position, created_at` order). `(project_id, position)` has a unique constraint to prevent collision from concurrent creates.

**Correction handling:**
- "actually make that a project" → LLM calls `convert_task_to_project(task_id=<last created>)`, which is now atomic (create project + delete task in a single commit — failure before commit leaves the task intact).
- This is in the system prompt as an explicit example so the model learns the pattern immediately.

**Consequences:**
- System prompt grows with workspace size; large workspaces (100+ tasks) may hit context limits. Mitigated by trimming `LLMContext` to the last 40 messages after each tool call.
- For demo scale (≤20 projects, ≤100 tasks) this is fine; for prod, switch to embedding-based retrieval.

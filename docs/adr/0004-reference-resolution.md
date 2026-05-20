# ADR 0004: LLM-based reference resolution with workspace snapshot

**Status:** Accepted

**Context:** Voice commands use deictic references: "that one", "the first task", "the finance one". Must resolve to entity IDs.

**Decision:** Inject the full workspace state (all projects + tasks with IDs, titles, positions) as a structured text block in the system prompt, refreshed after every tool call. The LLM resolves references itself using this snapshot.

**Alternatives rejected:**
- Dedicated resolver with regex/fuzzy-match — brittle, can't handle "that thing I just created"
- Embedding search over entity titles — overkill for small workspaces; latency cost

**`SessionState.recent`** tracks the rolling window of recently touched entities. The snapshot surfaces the "last touched" entity, which the LLM can use for "it" / "that one".

**Position field** on `Task` enables ordinal references: Task[0] = first task added to a project. The snapshot renders `TASK[0]`, `TASK[1]`, etc.

**Correction handling:**
- "actually make that a project" → LLM calls `convert_task_to_project(task_id=<last created>)`
- This is in the system prompt as an explicit example so the model learns the pattern immediately

**Consequences:**
- System prompt grows with workspace size; large workspaces (100+ tasks) may hit context limits
- For demo scale (≤20 projects, ≤100 tasks) this is fine; for prod, switch to embedding-based retrieval

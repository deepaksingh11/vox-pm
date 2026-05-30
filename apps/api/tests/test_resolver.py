"""SessionState reference resolution unit tests."""

from vox_pm.agent.state import EntityRef, SessionState


def make_state() -> SessionState:
    return SessionState(session_id="test")


def test_last_of_kind_project():
    state = make_state()
    state.touch(EntityRef(id="p1", title="Q2 Report", kind="project"))
    state.touch(EntityRef(id="t1", title="Draft intro", kind="task", project_id="p1"))
    assert state.last_of_kind("project") is not None
    assert state.last_of_kind("project").id == "p1"


def test_last_of_kind_task():
    state = make_state()
    state.touch(EntityRef(id="t1", title="Draft intro", kind="task"))
    state.touch(EntityRef(id="t2", title="Get numbers", kind="task"))
    last = state.last_of_kind("task")
    assert last is not None
    assert last.id == "t2"


def test_current_project_updated_on_project_touch():
    state = make_state()
    state.touch(EntityRef(id="p1", title="Project 1", kind="project"))
    assert state.current_project_id == "p1"
    state.touch(EntityRef(id="p2", title="Project 2", kind="project"))
    assert state.current_project_id == "p2"


def test_current_project_inherited_from_task():
    state = make_state()
    state.touch(EntityRef(id="t1", title="Task", kind="task", project_id="p1"))
    assert state.current_project_id == "p1"


def test_recent_deduplicates():
    state = make_state()
    state.touch(EntityRef(id="t1", title="Task", kind="task"))
    state.touch(EntityRef(id="t1", title="Task updated", kind="task"))
    assert sum(1 for r in state.recent if r.id == "t1") == 1


def test_snapshot_text_uses_aliases_not_raw_ids():
    """C1: snapshot uses stable P/T aliases, not raw UUIDs."""
    state = make_state()
    projects = [{"id": "p1", "title": "Q2 Report"}]
    tasks = [
        {"id": "t1", "title": "Draft intro", "project_id": "p1", "urgent": False, "due_at": None}
    ]
    snapshot = state.snapshot_text(projects, tasks)
    assert "Q2 Report" in snapshot
    assert "Draft intro" in snapshot
    assert "P1" in snapshot   # alias, not raw id
    assert "T1" in snapshot
    assert "p1" not in snapshot  # raw id must NOT appear


def test_snapshot_empty_workspace():
    state = make_state()
    snapshot = state.snapshot_text([], [])
    assert "empty" in snapshot


# ---------------------------------------------------------------------------
# C1: stable aliases across turns
# ---------------------------------------------------------------------------

def test_aliases_stable_across_snapshot_calls():
    """C1: aliases never renumber — T3 stays T3 even if earlier tasks are removed."""
    state = make_state()
    projects = [{"id": "proj", "title": "Work"}]
    tasks = [
        {"id": "t1", "title": "Draft intro", "project_id": "proj", "urgent": False, "due_at": None},
        {"id": "t2", "title": "Get numbers", "project_id": "proj", "urgent": False, "due_at": None},
        {"id": "t3", "title": "Review with Sarah", "project_id": "proj", "urgent": False, "due_at": None},
    ]
    # Turn 1: assign T1, T2, T3
    state.snapshot_text(projects, tasks)
    assert state.resolve_id("T3") == "t3"

    # Turn 2: t1 deleted — snapshot WITHOUT t1; T3 must still map to t3
    state.snapshot_text(projects, [tasks[1], tasks[2]])
    assert state.resolve_id("T3") == "t3"
    assert state.resolve_id("T2") == "t2"
    # T1 alias is now stale (entity gone) but should still resolve to "t1" (not reallocated)
    assert state.resolve_id("T1") == "t1"


def test_new_tasks_get_fresh_aliases_not_renumbered():
    """C1: a new task gets the next number, never reuses a prior alias."""
    state = make_state()
    projects = [{"id": "proj", "title": "Work"}]
    tasks_v1 = [
        {"id": "t1", "title": "Task A", "project_id": "proj", "urgent": False, "due_at": None},
        {"id": "t2", "title": "Task B", "project_id": "proj", "urgent": False, "due_at": None},
    ]
    state.snapshot_text(projects, tasks_v1)
    assert state.resolve_id("T1") == "t1"
    assert state.resolve_id("T2") == "t2"

    # t1 deleted, t3 added — new task gets T3, not T1
    tasks_v2 = [
        {"id": "t2", "title": "Task B", "project_id": "proj", "urgent": False, "due_at": None},
        {"id": "t3", "title": "Task C", "project_id": "proj", "urgent": False, "due_at": None},
    ]
    state.snapshot_text(projects, tasks_v2)
    assert state.resolve_id("T2") == "t2"
    assert state.resolve_id("T3") == "t3"
    # T1 still maps to the (now deleted) t1 — not reallocated to anything else
    assert state.resolve_id("T1") == "t1"


# ---------------------------------------------------------------------------
# C2: alias validation
# ---------------------------------------------------------------------------

def test_resolve_id_passthrough_for_full_uuid():
    """C2: non-alias strings pass through unchanged (assumed full UUID)."""
    state = make_state()
    full_uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert state.resolve_id(full_uuid) == full_uuid


def test_resolve_id_returns_uuid_for_known_alias():
    """C2: known alias resolves to the full UUID."""
    state = make_state()
    state.snapshot_text(
        [{"id": "proj-uuid", "title": "Work"}],
        [],
    )
    assert state.resolve_id("P1") == "proj-uuid"


def test_resolve_id_returns_none_for_unknown_alias():
    """C2: alias-shaped string not in the map returns None (unknown reference)."""
    state = make_state()
    state.snapshot_text(
        [{"id": "proj-uuid", "title": "Work"}],
        [],
    )
    # Only P1 is in the map; P9, T7 are unknown
    assert state.resolve_id("P9") is None
    assert state.resolve_id("T7") is None


def test_resolve_id_rejects_free_text_reference():
    """A free-text string (e.g. the LLM passing a project *title* as project_id) is NOT
    a valid reference — it must return None, not pass through to the DB (FK violation)."""
    state = make_state()
    assert state.resolve_id("Personal stuff") is None
    assert state.resolve_id("Psome-long-uuid-string") is None
    # Real UUIDs (e.g. an id echoed back from a prior tool result) still pass through.
    real_uuid = "550e8400-e29b-41d4-a716-446655440000"
    assert state.resolve_id(real_uuid) == real_uuid

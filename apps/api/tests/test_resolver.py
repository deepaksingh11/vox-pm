"""SessionState reference resolution unit tests."""

import pytest
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


def test_snapshot_text_includes_ids():
    state = make_state()
    projects = [{"id": "p1", "title": "Q2 Report"}]
    tasks = [
        {"id": "t1", "title": "Draft intro", "project_id": "p1", "urgent": False, "due_at": None}
    ]
    snapshot = state.snapshot_text(projects, tasks)
    assert "p1" in snapshot
    assert "Q2 Report" in snapshot
    assert "Draft intro" in snapshot


def test_snapshot_empty_workspace():
    state = make_state()
    snapshot = state.snapshot_text([], [])
    assert "empty" in snapshot

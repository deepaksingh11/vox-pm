"""Tool definitions and handlers for the PM agent."""

from datetime import datetime
from typing import Any

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema

from vox_pm.agent.state import EntityRef, SessionState, get_state
from vox_pm.db import get_session_factory
from vox_pm.events.bus import publish
from vox_pm.services import projects as project_svc
from vox_pm.services import tasks as task_svc


# Legacy dict format kept for register_function() name iteration only
TOOL_DEFINITIONS = [
    {
        "name": "create_project",
        "description": "Create a new project.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Project title"}},
            "required": ["title"],
        },
    },
    {
        "name": "update_project",
        "description": "Update an existing project by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "delete_project",
        "description": "Delete a project by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "create_task",
        "description": "Create a new task, optionally inside a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "project_id": {"type": "string", "description": "Project to add task to"},
                "description": {"type": "string"},
                "urgent": {"type": "boolean", "default": False},
                "due_at": {"type": "string", "format": "date-time", "description": "ISO 8601"},
                "reminder_at": {"type": "string", "format": "date-time"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update fields on an existing task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "urgent": {"type": "boolean"},
                "due_at": {"type": "string", "format": "date-time"},
                "reminder_at": {"type": "string", "format": "date-time"},
                "status": {"type": "string", "enum": ["open", "in_progress", "blocked", "cancelled", "done"]},
            },
            "required": ["id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Delete a task by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "move_task",
        "description": "Move a task to a different project (or to unassigned if project_id is null).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "project_id": {"type": "string"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "convert_task_to_project",
        "description": "Delete a task and create a project with the same title.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "ask_clarification",
        "description": "Ask the user to clarify when genuinely ambiguous.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Possible entities the user might mean",
                },
            },
            "required": ["question"],
        },
    },
]

# ToolsSchema used by all LLM providers (Pipecat 1.2+)
TOOLS_SCHEMA = ToolsSchema(
    standard_tools=[
        FunctionSchema(
            name=t["name"],
            description=t["description"],
            properties=t["input_schema"]["properties"],
            required=t["input_schema"].get("required", []),
        )
        for t in TOOL_DEFINITIONS
    ]
)


def _parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


async def dispatch_tool(
    name: str,
    args: dict[str, Any],
    session_id: str,
) -> dict[str, Any]:
    """Execute a tool call. Returns result dict for LLM context."""
    state = get_state(session_id)

    # Resolve short aliases (P1, T3, …) → full UUIDs in any id field
    for key in ("id", "task_id", "project_id"):
        if key in args and isinstance(args[key], str):
            args[key] = state.resolve_id(args[key])

    factory = get_session_factory()

    async with factory() as db:
        match name:
            case "create_project":
                result = await project_svc.create_project(db, args["title"], session_id)
                state.touch(EntityRef(id=result.id, title=result.title, kind="project"))
                return {"ok": True, "id": result.id, "title": result.title}

            case "update_project":
                result = await project_svc.update_project(
                    db, args["id"], title=args.get("title"), session_id=session_id
                )
                if result:
                    state.touch(EntityRef(id=result.id, title=result.title, kind="project"))
                return {"ok": result is not None}

            case "delete_project":
                ok = await project_svc.delete_project(db, args["id"], session_id)
                if state.current_project_id == args["id"]:
                    state.current_project_id = None
                return {"ok": ok}

            case "create_task":
                result = await task_svc.create_task(
                    db,
                    title=args["title"],
                    project_id=args.get("project_id") or state.current_project_id,
                    description=args.get("description"),
                    urgent=args.get("urgent", False),
                    due_at=_parse_dt(args.get("due_at")),
                    reminder_at=_parse_dt(args.get("reminder_at")),
                    session_id=session_id,
                )
                state.touch(EntityRef(
                    id=result.id,
                    title=result.title,
                    kind="task",
                    project_id=result.project_id,
                ))
                return {"ok": True, "id": result.id, "title": result.title}

            case "update_task":
                task_id = args.pop("id", None)
                if not task_id:
                    return {"ok": False, "error": "id required"}
                if "due_at" in args:
                    args["due_at"] = _parse_dt(args["due_at"])
                if "reminder_at" in args:
                    args["reminder_at"] = _parse_dt(args["reminder_at"])
                result = await task_svc.update_task(db, task_id, session_id, **args)
                if result:
                    state.touch(EntityRef(
                        id=result.id, title=result.title, kind="task", project_id=result.project_id
                    ))
                return {"ok": result is not None}

            case "delete_task":
                ok = await task_svc.delete_task(db, args["id"], session_id)
                return {"ok": ok}

            case "move_task":
                result = await task_svc.move_task(
                    db, args["task_id"], args.get("project_id"), session_id
                )
                if result:
                    state.touch(EntityRef(
                        id=result.id, title=result.title, kind="task", project_id=result.project_id
                    ))
                return {"ok": result is not None}

            case "convert_task_to_project":
                task_id_raw = args.get("task_id")
                if not task_id_raw:
                    return {"ok": False, "error": "task_id required"}
                task = await task_svc.get_task(db, task_id_raw)
                if not task:
                    return {"ok": False, "error": "task not found"}
                title = task.title
                await task_svc.delete_task(db, task_id_raw, session_id)
                result = await project_svc.create_project(db, title, session_id)
                state.touch(EntityRef(id=result.id, title=result.title, kind="project"))
                return {"ok": True, "id": result.id, "title": result.title}

            case "ask_clarification":
                await publish(
                    session_id,
                    "clarification.ask",
                    {"question": args["question"], "candidates": args.get("candidates", [])},
                )
                return {"ok": True}

            case _:
                return {"ok": False, "error": f"unknown tool: {name}"}

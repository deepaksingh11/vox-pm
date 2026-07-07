"""Pydantic validation models for LLM-emitted tool arguments.

The LLM produces tool calls as free-form dicts. Validating them against a strict
schema *before* any reference resolution or DB work stops malformed arguments
(wrong types, bad status enums, unknown fields) from reaching the service layer,
and yields a readable error string the LLM can act on.

Dates stay as `str` here — `tools._parse_dt` owns ISO 8601 parsing + timezone
normalization. These models enforce the type/enum contract, not date semantics.
"""

from pydantic import BaseModel, ConfigDict, Field

from vox_pm.schemas import DESCRIPTION_MAX, TITLE_MAX, TaskStatus


class _StrictArgs(BaseModel):
    # Reject unknown fields so a hallucinated argument is surfaced, not silently dropped.
    model_config = ConfigDict(extra="forbid")


class CreateProjectArgs(_StrictArgs):
    title: str = Field(min_length=1, max_length=TITLE_MAX)


class UpdateProjectArgs(_StrictArgs):
    id: str
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX)


class DeleteProjectArgs(_StrictArgs):
    id: str


class CreateTaskArgs(_StrictArgs):
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    project_id: str | None = None
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    urgent: bool = False
    due_at: str | None = None
    reminder_at: str | None = None


class UpdateTaskArgs(_StrictArgs):
    id: str
    title: str | None = Field(default=None, min_length=1, max_length=TITLE_MAX)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    urgent: bool | None = None
    due_at: str | None = None
    reminder_at: str | None = None
    status: TaskStatus | None = None


class DeleteTaskArgs(_StrictArgs):
    id: str


class MoveTaskArgs(_StrictArgs):
    task_id: str
    project_id: str | None = None


class ConvertTaskToProjectArgs(_StrictArgs):
    task_id: str


class AskClarificationArgs(_StrictArgs):
    question: str
    candidates: list[str] = []


ARG_MODELS: dict[str, type[_StrictArgs]] = {
    "create_project": CreateProjectArgs,
    "update_project": UpdateProjectArgs,
    "delete_project": DeleteProjectArgs,
    "create_task": CreateTaskArgs,
    "update_task": UpdateTaskArgs,
    "delete_task": DeleteTaskArgs,
    "move_task": MoveTaskArgs,
    "convert_task_to_project": ConvertTaskToProjectArgs,
    "ask_clarification": AskClarificationArgs,
}


def validate_args(name: str, args: dict) -> tuple[dict | None, str | None]:
    """Validate raw tool args against the tool's model.

    Returns (validated_args, None) on success, or (None, error_message) on failure.
    Unknown tool names pass through unchanged (handled later in dispatch).
    """
    model = ARG_MODELS.get(name)
    if model is None:
        return args, None
    from pydantic import ValidationError

    try:
        validated = model.model_validate(args)
    except ValidationError as exc:
        errs = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return None, f"invalid arguments for {name}: {errs}"
    # exclude_unset keeps "absent vs explicit None" distinct — critical for update_task,
    # where an absent field must not be touched but an explicit None must clear it.
    return validated.model_dump(exclude_unset=True), None

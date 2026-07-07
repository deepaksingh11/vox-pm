"""Pipecat pipeline factory per voice session."""

import asyncio
import time

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    TranscriptionFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from vox_pm.agent.llm.factory import build_llm_service
from vox_pm.agent.prompts import build_system_prompt
from vox_pm.agent.state import clear_state, get_state
from vox_pm.agent.tools import dispatch_tool
from vox_pm.config import get_settings
from vox_pm.db import get_session_factory
from vox_pm.events.bus import publish
from vox_pm.services.projects import list_projects
from vox_pm.services.tasks import list_tasks

_MAX_CONTEXT_MESSAGES = 40  # system + last 40 user/assistant messages


async def _get_context_snapshot(session_id: str) -> str:
    factory = get_session_factory()
    async with factory() as db:
        projects = await list_projects(db)
        tasks = await list_tasks(db)
    project_dicts = [p.model_dump(mode="json") for p in projects]
    task_dicts = [t.model_dump(mode="json") for t in tasks]
    state = get_state(session_id)
    return state.snapshot_text(project_dicts, task_dicts)


def _trim_context(context: LLMContext) -> None:
    msgs = context.messages
    if len(msgs) <= _MAX_CONTEXT_MESSAGES + 1:
        return
    # Keep system message (index 0) + roughly the most recent _MAX_CONTEXT_MESSAGES
    # messages — but never cut between an assistant "tool_calls" message and its
    # role:"tool" results: providers require the pair intact (Anthropic 400s on an
    # orphaned tool_result). A plain user message is always a safe cut boundary, so
    # advance the cut point forward to the next one.
    start = len(msgs) - _MAX_CONTEXT_MESSAGES
    while start < len(msgs):
        m = msgs[start]
        if isinstance(m, dict) and m.get("role") == "user":
            break
        start += 1
    if start >= len(msgs) or start <= 1:
        return  # no safe boundary (or nothing to cut) — skip trimming this round
    del msgs[1:start]


async def refresh_system_prompt(
    session_id: str, context: LLMContext, ctx_lock: asyncio.Lock
) -> None:
    """Rebuild the system message (workspace snapshot) from the DB, in place.

    Called both after every tool and at the start of every user turn. The turn-start
    call is what keeps the LLM consistent with the DB after a barge-in: a tool the
    framework marked "CANCELLED" whose shielded write actually committed shows up here.
    Serialized via ctx_lock since concurrent tool calls share context.messages.
    """
    async with ctx_lock:
        try:
            snapshot = await _get_context_snapshot(session_id)
            messages = context.messages
            if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
                messages[0]["content"] = build_system_prompt(snapshot)
        except Exception as exc:
            logger.warning(f"snapshot refresh failed: {exc}")
        # Trim context to prevent unbounded growth over long sessions.
        _trim_context(context)


def _make_tool_handler(session_id: str, context: LLMContext, ctx_lock: asyncio.Lock):
    async def handle(params: FunctionCallParams) -> None:
        name = params.function_name
        args = dict(params.arguments)
        t0 = time.monotonic()

        logger.info(f"tool.started name={name} args={args}")
        await publish(session_id, "tool.started", {"name": name, "arguments": args})

        # Run dispatch as its own task and await it shielded: if a barge-in interruption
        # cancels this handler, the shield lets the DB write + its entity WS events run to
        # completion (no half-written / lost state) instead of being abandoned mid-commit.
        task = asyncio.ensure_future(dispatch_tool(name, args, session_id))
        try:
            # 30 s hard timeout guards against a hung DB call or LLM non-response.
            result = await asyncio.wait_for(asyncio.shield(task), timeout=30.0)
            duration_ms = round((time.monotonic() - t0) * 1000)
            logger.info(f"tool.completed name={name} duration_ms={duration_ms} result={result}")
            await publish(session_id, "tool.completed", {"name": name, "result": result, "duration_ms": duration_ms})
        except TimeoutError:
            # A genuine hang (not an interruption) — abort the dispatch task explicitly,
            # since shield kept wait_for's timeout from cancelling it.
            task.cancel()
            duration_ms = 30_000
            error = f"{name} timed out after 30s"
            logger.error(f"tool.timeout name={name}")
            await publish(session_id, "tool.failed", {"name": name, "error": error, "duration_ms": duration_ms})
            result = {"ok": False, "error": error}
        except asyncio.CancelledError:
            # Barge-in: Pipecat cancelled this handler. `task` is shielded, so the write +
            # its entity event still complete (frontend sees the create). Pipecat marks the
            # LLM tool result "CANCELLED"; refresh_system_prompt on the next user turn (Fix 2)
            # reconciles the LLM's view with the committed DB state. Re-raise promptly so
            # Pipecat's cancellation unwinds cleanly.
            task.add_done_callback(_log_task_exc)
            logger.warning(f"tool.cancelled name={name} (interrupted; shielded write completing)")
            raise
        except Exception as exc:
            duration_ms = round((time.monotonic() - t0) * 1000)
            error = str(exc)
            logger.error(f"tool.failed name={name} error={error} duration_ms={duration_ms}")
            await publish(session_id, "tool.failed", {"name": name, "error": error, "duration_ms": duration_ms})
            result = {"ok": False, "error": error}

        await refresh_system_prompt(session_id, params.context or context, ctx_lock)
        await params.result_callback(result)

    return handle


async def run_pipeline(session_id: str, room_url: str, token: str) -> None:
    settings = get_settings()

    transport = DailyTransport(
        room_url,
        token,
        "Vox PM",
        DailyParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        settings=DeepgramSTTService.Settings(
            model="nova-3",
            language="en-US",
            smart_format=True,
            numerals=True,
            interim_results=True,
            endpointing=300,
        ),
    )

    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        settings=CartesiaTTSService.Settings(voice=settings.cartesia_voice_id),
    )

    snapshot = await _get_context_snapshot(session_id)
    context = LLMContext()
    context.add_message({"role": "system", "content": build_system_prompt(snapshot)})

    ctx_lock = asyncio.Lock()  # Serializes concurrent tool-handler context mutations.
    tool_handler = _make_tool_handler(session_id, context, ctx_lock)
    llm = build_llm_service(context, tool_handler, settings)

    context_pair = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            _TranscriptPublisher(session_id, context, ctx_lock),
            context_pair.user(),
            llm,
            tts,
            transport.output(),
            context_pair.assistant(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_left")
    async def on_left(transport, **kwargs):
        await task.cancel()

    runner = PipelineRunner(handle_sigint=False)
    try:
        await runner.run(task)
    finally:
        clear_state(session_id)


def _log_task_exc(t: asyncio.Task) -> None:
    if not t.cancelled() and (exc := t.exception()):
        logger.error(f"transcript publish error: {exc}")


class _TranscriptPublisher(FrameProcessor):
    """Passes all frames through; side-publishes STT transcripts to the event bus and
    refreshes the system-prompt snapshot at the start of each user turn (on the final
    transcript) so the LLM always sees ground-truth DB state — reconciling any tool the
    framework marked CANCELLED on a barge-in whose shielded write actually committed."""

    def __init__(self, session_id: str, context: LLMContext, ctx_lock: asyncio.Lock):
        super().__init__()
        self._session_id = session_id
        self._context = context
        self._ctx_lock = ctx_lock
        # Keep strong refs to in-flight tasks so they aren't GC'd mid-flight.
        self._tasks: set[asyncio.Task] = set()

    def _fire(self, coro) -> None:
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)
        t.add_done_callback(_log_task_exc)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InterimTranscriptionFrame):
            self._fire(publish(self._session_id, "transcript.partial", {"text": frame.text}))
        elif isinstance(frame, TranscriptionFrame):
            self._fire(publish(self._session_id, "transcript.final", {"text": frame.text}))
            # Refresh BEFORE pushing downstream so the context aggregator + LLM read the
            # fresh system message this turn. Awaited (not fire-and-forget) for that ordering.
            await refresh_system_prompt(self._session_id, self._context, self._ctx_lock)
        await self.push_frame(frame, direction)

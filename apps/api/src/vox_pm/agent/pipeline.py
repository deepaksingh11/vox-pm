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
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
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
    # Keep system message (index 0) + the most recent _MAX_CONTEXT_MESSAGES messages
    del msgs[1 : len(msgs) - _MAX_CONTEXT_MESSAGES]


def _make_tool_handler(session_id: str, context: LLMContext):
    async def handle(params: FunctionCallParams) -> None:
        name = params.function_name
        args = dict(params.arguments)
        t0 = time.monotonic()

        logger.info(f"tool.started name={name} args={args}")
        await publish(session_id, "tool.started", {"name": name, "arguments": args})

        try:
            # M11: 30s hard timeout on tool dispatch (DB + LLM ops)
            result = await asyncio.wait_for(
                dispatch_tool(name, args, session_id),
                timeout=30.0,
            )
            duration_ms = round((time.monotonic() - t0) * 1000)
            logger.info(f"tool.completed name={name} duration_ms={duration_ms} result={result}")
            await publish(session_id, "tool.completed", {"name": name, "result": result, "duration_ms": duration_ms})
        except asyncio.TimeoutError:
            duration_ms = 30_000
            error = f"{name} timed out after 30s"
            logger.error(f"tool.timeout name={name}")
            await publish(session_id, "tool.failed", {"name": name, "error": error, "duration_ms": duration_ms})
            result = {"ok": False, "error": error}
        except Exception as exc:
            duration_ms = round((time.monotonic() - t0) * 1000)
            error = str(exc)
            logger.error(f"tool.failed name={name} error={error} duration_ms={duration_ms}")
            await publish(session_id, "tool.failed", {"name": name, "error": error, "duration_ms": duration_ms})
            result = {"ok": False, "error": error}

        try:
            snapshot = await _get_context_snapshot(session_id)
            messages = (params.context or context).messages
            if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
                messages[0]["content"] = build_system_prompt(snapshot)
        except Exception as exc:
            logger.warning(f"snapshot refresh failed: {exc}")

        # M6: trim context to prevent unbounded growth over long sessions
        _trim_context(params.context or context)

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
        voice_id=settings.cartesia_voice_id,
    )

    snapshot = await _get_context_snapshot(session_id)
    context = LLMContext()
    context.add_message({"role": "system", "content": build_system_prompt(snapshot)})

    tool_handler = _make_tool_handler(session_id, context)
    llm = build_llm_service(context, tool_handler, settings)

    context_pair = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            _TranscriptPublisher(session_id),
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
    """Passes all frames through; side-publishes STT transcripts to event bus."""

    def __init__(self, session_id: str):
        super().__init__()
        self._session_id = session_id
        # M1: keep strong refs so tasks aren't GC'd mid-flight
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
        await self.push_frame(frame, direction)

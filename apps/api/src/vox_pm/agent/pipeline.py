"""Pipecat pipeline factory per voice session."""

import asyncio

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
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from vox_pm.agent.prompts import build_system_prompt
from vox_pm.agent.state import get_state
from vox_pm.agent.tools import dispatch_tool
from vox_pm.config import get_settings
from vox_pm.db import get_session_factory
from vox_pm.events.bus import publish
from vox_pm.services.projects import list_projects
from vox_pm.services.tasks import list_tasks


async def _get_context_snapshot(session_id: str) -> str:
    factory = get_session_factory()
    async with factory() as db:
        projects = await list_projects(db)
        tasks = await list_tasks(db)
    project_dicts = [p.model_dump(mode="json") for p in projects]
    task_dicts = [t.model_dump(mode="json") for t in tasks]
    state = get_state(session_id)
    return state.snapshot_text(project_dicts, task_dicts)


def _build_tool_handler(session_id: str, context: LLMContext):
    async def handle(function_name, tool_call_id, args, llm, ctx, result_callback):
        await publish(session_id, "agent.thinking", {})
        result = await dispatch_tool(function_name, dict(args), session_id)

        # Refresh system prompt with updated workspace snapshot after each tool call
        snapshot = await _get_context_snapshot(session_id)
        messages = ctx.messages if ctx else context.messages
        if messages and isinstance(messages[0], dict) and messages[0].get("role") == "system":
            messages[0]["content"] = build_system_prompt(snapshot)

        await result_callback(result)

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
        ),
    )

    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        live_options={
            "model": "nova-3",
            "language": "en-US",
            "smart_format": True,
            "interim_results": True,
            "endpointing": 300,
        },
    )

    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        voice_id=settings.cartesia_voice_id,
    )

    snapshot = await _get_context_snapshot(session_id)
    context = LLMContext()
    context.add_message({"role": "system", "content": build_system_prompt(snapshot)})

    llm = _build_llm_service(settings, context, session_id)

    context_pair = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    transcript_publisher = _TranscriptPublisher(session_id)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript_publisher,
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
    await runner.run(task)


def _build_llm_service(settings, context: LLMContext, session_id: str):
    from vox_pm.agent.tools import TOOL_DEFINITIONS, OPENAI_TOOL_DEFINITIONS

    handler = _build_tool_handler(session_id, context)

    provider = settings.llm_provider
    if not provider:
        provider = "anthropic" if settings.anthropic_api_key else "openai"

    if provider == "anthropic":
        from pipecat.services.anthropic.llm import AnthropicLLMService

        context.set_tools(TOOL_DEFINITIONS)
        llm = AnthropicLLMService(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
        for tool in TOOL_DEFINITIONS:
            llm.register_function(tool["name"], handler)
        return llm

    else:
        from pipecat.services.openai.llm import OpenAILLMService

        context.set_tools(OPENAI_TOOL_DEFINITIONS)
        llm = OpenAILLMService(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        for tool in TOOL_DEFINITIONS:
            llm.register_function(tool["name"], handler)
        return llm


class _TranscriptPublisher(FrameProcessor):
    """Passes all frames through; side-publishes STT transcripts to event bus."""

    def __init__(self, session_id: str):
        super().__init__()
        self._session_id = session_id

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, InterimTranscriptionFrame):
            asyncio.create_task(
                publish(self._session_id, "transcript.partial", {"text": frame.text})
            )
        elif isinstance(frame, TranscriptionFrame):
            asyncio.create_task(
                publish(self._session_id, "transcript.final", {"text": frame.text})
            )
        await self.push_frame(frame, direction)

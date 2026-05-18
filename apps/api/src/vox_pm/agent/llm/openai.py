from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.openai.llm import OpenAILLMService

from vox_pm.agent.tools import TOOL_DEFINITIONS, TOOLS_SCHEMA
from vox_pm.config import Settings


def build(context: LLMContext, tool_handler, settings: Settings):
    context.set_tools(TOOLS_SCHEMA)
    llm = OpenAILLMService(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )
    for tool in TOOL_DEFINITIONS:
        llm.register_function(tool["name"], tool_handler)
    return llm

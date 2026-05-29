from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.services.anthropic.llm import AnthropicLLMService

from vox_pm.agent.tools import TOOL_DEFINITIONS, TOOLS_SCHEMA
from vox_pm.config import Settings


def build(context: LLMContext, tool_handler, settings: Settings):
    context.set_tools(TOOLS_SCHEMA)
    llm = AnthropicLLMService(
        api_key=settings.anthropic_api_key or "",  # factory guards key presence before build()
        model=settings.anthropic_model,
    )
    for tool in TOOL_DEFINITIONS:
        llm.register_function(tool["name"], tool_handler)
    return llm

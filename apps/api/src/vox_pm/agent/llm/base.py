from typing import Protocol, Any
from pipecat.processors.aggregators.llm_context import LLMContext


class LLMProviderBuilder(Protocol):
    """Build a Pipecat LLM service wired with tool handlers."""

    def build(
        self,
        context: LLMContext,
        tool_handler: Any,
    ): ...

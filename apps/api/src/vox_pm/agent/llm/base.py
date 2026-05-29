from typing import Protocol, Any
from pipecat.processors.aggregators.llm_context import LLMContext


class LLMProviderBuilder(Protocol):
    """Module-level build function signature shared by all LLM provider modules."""

    def __call__(
        self,
        context: LLMContext,
        tool_handler: Any,
        settings: Any,
    ): ...

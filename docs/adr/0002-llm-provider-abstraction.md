# ADR 0002: LLM provider abstraction via env config

**Status:** Accepted

**Context:** Anthropic Claude and OpenAI GPT-4o both support streaming tool calls. Evaluators may have either key.

**Decision:** `agent/llm/factory.py` selects provider from `LLM_PROVIDER` env var, falling back to whichever API key is present. Both `AnthropicLLMService` and `OpenAILLMService` register the same function handlers.

**Reasons:**
- Zero-friction onboarding for evaluators regardless of which key they have
- Pipecat ships first-class services for both; wrapping is thin

**Consequences:**
- Tool definitions must be maintained in both Anthropic and OpenAI formats (`TOOL_DEFINITIONS` and `OPENAI_TOOL_DEFINITIONS` in `tools.py`)
- Claude's tool-calling is generally more reliable for multi-step instructions; default Anthropic if both keys present

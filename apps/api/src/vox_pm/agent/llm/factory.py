"""Select LLM provider by walking the ordered list in settings.llm_provider_order.
First entry whose API key is present wins."""

from pipecat.processors.aggregators.llm_context import LLMContext

from vox_pm.config import Settings

# Map name → (module, key_attr)
_PROVIDERS: dict[str, tuple[str, str]] = {
    "anthropic": ("vox_pm.agent.llm.anthropic", "anthropic_api_key"),
    "openai":    ("vox_pm.agent.llm.openai",    "openai_api_key"),
    "gemini":    ("vox_pm.agent.llm.gemini",     "google_api_key"),
}


def build_llm_service(context: LLMContext, tool_handler, settings: Settings):
    for name in settings.llm_provider_order:
        entry = _PROVIDERS.get(name)
        if not entry:
            continue
        module_path, key_attr = entry
        if not getattr(settings, key_attr, None):
            continue
        import importlib
        module = importlib.import_module(module_path)
        return module.build(context, tool_handler, settings)

    configured = [n for n in settings.llm_provider_order if n in _PROVIDERS]
    raise RuntimeError(
        f"No LLM API key found. Checked providers in order: {configured}. "
        "Set at least one of ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY."
    )

from ...core.config_manager import Config
from .providers import GeminiProvider, OpenAICompatibleProvider


def get_provider():
    provider = str(getattr(Config, "TNPSC_AI_PROVIDER", "openrouter")).lower()
    timeout = int(getattr(Config, "TNPSC_AI_TIMEOUT_SECONDS", 60) or 60)
    if provider == "ollama":
        return OpenAICompatibleProvider("ollama", Config.OLLAMA_BASE_URL, "", Config.OLLAMA_MODEL, timeout)
    if provider == "gemini":
        return GeminiProvider(Config.GEMINI_API_KEY, Config.GEMINI_MODEL, timeout)
    return OpenAICompatibleProvider("openrouter", Config.OPENROUTER_BASE_URL, Config.OPENROUTER_API_KEY, Config.TNPSC_AI_MODEL, timeout)

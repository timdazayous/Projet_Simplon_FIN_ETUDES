"""LLM service: one OpenAI-compatible client, Groq first, optional Ollama fallback."""

from src.llm.client import LLMClient, LLMError, LLMResult
from src.llm.config import ConfigError, LLMConfig, ProviderConfig, load_config

__all__ = [
    "ConfigError",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LLMResult",
    "ProviderConfig",
    "load_config",
]

"""Configuration of the LLM service, loaded from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

PROVIDERS = ("groq", "ollama")
DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_BACKOFF_MAX_SECONDS = 30.0
# Ollama ignores the API key but the OpenAI SDK requires a non-empty one.
OLLAMA_DUMMY_KEY = "ollama"


class ConfigError(ValueError):
    """Raised when the configuration is missing a value or has an invalid one."""


@dataclass(frozen=True)
class ProviderConfig:
    """Connection settings of one provider."""

    name: str
    base_url: str
    model: str
    api_key: str = ""

    def __repr__(self) -> str:  # never show the key
        return f"ProviderConfig(name={self.name!r}, model={self.model!r})"


@dataclass(frozen=True)
class LLMConfig:
    """Full configuration: primary provider, optional fallback, retry policy."""

    primary: ProviderConfig
    fallback: ProviderConfig | None
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS
    backoff_max_seconds: float = DEFAULT_BACKOFF_MAX_SECONDS


def _provider(name: str, env: Mapping[str, str]) -> ProviderConfig:
    """Build and validate the settings of one provider."""
    prefix = name.upper()
    required = [f"{prefix}_BASE_URL", f"{prefix}_MODEL"]
    if name == "groq":
        required.append("GROQ_API_KEY")
    missing = [var for var in required if not (env.get(var) or "").strip()]
    if missing:
        raise ConfigError(f"Missing environment variable(s) for {name}: {', '.join(missing)}")
    api_key = (env.get("GROQ_API_KEY") or "").strip() if name == "groq" else OLLAMA_DUMMY_KEY
    return ProviderConfig(
        name=name,
        base_url=env[f"{prefix}_BASE_URL"].strip(),
        model=env[f"{prefix}_MODEL"].strip(),
        api_key=api_key,
    )


def _number(env: Mapping[str, str], var: str, default: float, cast: type) -> float:
    """Read a non-negative number from the environment, or return the default."""
    raw = (env.get(var) or "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        raise ConfigError(f"{var} must be a number, got {raw!r}") from None
    if value < 0:
        raise ConfigError(f"{var} must be >= 0, got {raw!r}")
    return value


def load_config(env: Mapping[str, str] | None = None) -> LLMConfig:
    """Load and validate the configuration.

    Without argument, reads ``os.environ`` after loading a ``.env`` file if present.
    Only the providers actually used (primary and fallback) are validated.
    """
    if env is None:
        load_dotenv()
        env = os.environ

    primary_name = (env.get("LLM_PROVIDER") or "groq").strip().lower()
    fallback_name = (env.get("LLM_FALLBACK_PROVIDER") or "").strip().lower()
    for var, name in (("LLM_PROVIDER", primary_name), ("LLM_FALLBACK_PROVIDER", fallback_name)):
        if name and name not in PROVIDERS:
            raise ConfigError(f"{var} must be one of {PROVIDERS}, got {name!r}")
    if fallback_name == primary_name:
        raise ConfigError("LLM_FALLBACK_PROVIDER must differ from LLM_PROVIDER (or be empty)")

    return LLMConfig(
        primary=_provider(primary_name, env),
        fallback=_provider(fallback_name, env) if fallback_name else None,
        max_retries=int(_number(env, "LLM_MAX_RETRIES", DEFAULT_MAX_RETRIES, int)),
        backoff_base_seconds=_number(
            env, "LLM_BACKOFF_BASE_SECONDS", DEFAULT_BACKOFF_BASE_SECONDS, float
        ),
        backoff_max_seconds=_number(
            env, "LLM_BACKOFF_MAX_SECONDS", DEFAULT_BACKOFF_MAX_SECONDS, float
        ),
    )

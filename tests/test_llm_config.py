"""Tests of the LLM configuration (no network, no .env file read)."""

import pytest

from src.llm import ConfigError, load_config

GROQ_ENV = {
    "LLM_PROVIDER": "groq",
    "GROQ_API_KEY": "gsk_test_key",
    "GROQ_BASE_URL": "https://groq.example/v1",
    "GROQ_MODEL": "model-g",
}
OLLAMA_ENV = {"OLLAMA_BASE_URL": "http://localhost:11434/v1", "OLLAMA_MODEL": "model-o"}


def test_loads_groq_without_fallback():
    config = load_config(GROQ_ENV)
    assert config.primary.name == "groq"
    assert config.primary.model == "model-g"
    assert config.fallback is None
    assert config.max_retries == 5
    assert config.backoff_base_seconds == 2.0


def test_loads_fallback_and_retry_settings():
    env = {
        **GROQ_ENV,
        **OLLAMA_ENV,
        "LLM_FALLBACK_PROVIDER": "ollama",
        "LLM_MAX_RETRIES": "3",
        "LLM_BACKOFF_BASE_SECONDS": "0.5",
        "LLM_BACKOFF_MAX_SECONDS": "10",
    }
    config = load_config(env)
    assert config.fallback is not None and config.fallback.name == "ollama"
    assert config.fallback.api_key  # dummy key required by the SDK
    assert (config.max_retries, config.backoff_base_seconds, config.backoff_max_seconds) == (
        3,
        0.5,
        10.0,
    )


def test_empty_fallback_means_no_fallback():
    assert load_config({**GROQ_ENV, "LLM_FALLBACK_PROVIDER": ""}).fallback is None


def test_ollama_primary_needs_no_api_key():
    config = load_config({"LLM_PROVIDER": "ollama", **OLLAMA_ENV})
    assert config.primary.name == "ollama"


def test_missing_groq_key_gives_clear_error():
    env = {k: v for k, v in GROQ_ENV.items() if k != "GROQ_API_KEY"}
    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        load_config(env)


def test_missing_fallback_settings_are_reported():
    with pytest.raises(ConfigError, match="OLLAMA_MODEL"):
        load_config({**GROQ_ENV, "LLM_FALLBACK_PROVIDER": "ollama"})


@pytest.mark.parametrize(
    "extra",
    [
        {"LLM_PROVIDER": "openai"},
        {"LLM_FALLBACK_PROVIDER": "groq"},  # same as primary
        {"LLM_FALLBACK_PROVIDER": "nope"},
        {"LLM_MAX_RETRIES": "abc"},
        {"LLM_MAX_RETRIES": "-1"},
    ],
)
def test_invalid_values_are_rejected(extra):
    with pytest.raises(ConfigError):
        load_config({**GROQ_ENV, **OLLAMA_ENV, **extra})


def test_api_key_is_not_in_repr():
    assert "gsk_test_key" not in repr(load_config(GROQ_ENV))


def test_default_source_is_os_environ(monkeypatch):
    monkeypatch.setattr("src.llm.config.load_dotenv", lambda: None)  # do not read any .env
    for key, value in GROQ_ENV.items():
        monkeypatch.setenv(key, value)
    assert load_config().primary.model == "model-g"

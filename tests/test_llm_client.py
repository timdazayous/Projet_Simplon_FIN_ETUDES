"""Tests of the LLM client with a simulated OpenAI SDK (no network)."""

import logging
from types import SimpleNamespace

import httpx2 as httpx
import openai
import pytest

from src.llm import LLMClient, LLMConfig, LLMError, ProviderConfig

SECRET_PROMPT = "Le mot de passe de Jean Dupont est hunter2"
SECRET_ANSWER = "Reponse confidentielle XYZ"

GROQ = ProviderConfig("groq", "https://groq.example/v1", "model-g", "key")
OLLAMA = ProviderConfig("ollama", "http://localhost:11434/v1", "model-o", "ollama")


def rate_limit(retry_after: str | None = None) -> openai.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    request = httpx.Request("POST", "https://groq.example/v1/chat/completions")
    response = httpx.Response(429, headers=headers, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


def server_error() -> openai.InternalServerError:
    request = httpx.Request("POST", "https://groq.example/v1/chat/completions")
    response = httpx.Response(503, request=request)
    return openai.InternalServerError("boom", response=response, body=None)


def reply(text: str = SECRET_ANSWER):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
    )


class FakeSDK:
    """Plays a script of outcomes (exceptions are raised, other values returned)."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_client(sdks, *, fallback=False, max_retries=2):
    config = LLMConfig(
        primary=GROQ,
        fallback=OLLAMA if fallback else None,
        max_retries=max_retries,
        backoff_base_seconds=1.0,
        backoff_max_seconds=10.0,
    )
    sleeps: list[float] = []
    client = LLMClient(config, client_factory=lambda p: sdks[p.name], sleep=sleeps.append)
    return client, sleeps


def test_simple_success_returns_metadata():
    groq = FakeSDK([reply()])
    client, sleeps = make_client({"groq": groq})
    result = client.complete(SECRET_PROMPT)
    assert result.text == SECRET_ANSWER
    assert (result.provider, result.model) == ("groq", "model-g")
    assert (result.input_tokens, result.output_tokens) == (12, 7)
    assert result.latency_ms >= 0
    assert sleeps == []


def test_missing_usage_and_content_are_tolerated():
    bare = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=None))], usage=None
    )
    client, _ = make_client({"groq": FakeSDK([bare])})
    result = client.complete("x")
    assert (result.text, result.input_tokens, result.output_tokens) == ("", 0, 0)


def test_retry_on_429_then_success_with_exponential_backoff():
    groq = FakeSDK([rate_limit(), rate_limit(), reply()])
    client, sleeps = make_client({"groq": groq})
    assert client.complete("x").provider == "groq"
    assert groq.calls == 3
    assert sleeps == [1.0, 2.0]


def test_retry_after_header_is_honored_and_delay_capped():
    groq = FakeSDK([rate_limit("5"), rate_limit("999"), reply()])
    client, sleeps = make_client({"groq": groq})
    client.complete("x")
    assert sleeps == [5.0, 10.0]  # max(backoff, retry-after), capped at 10


def test_invalid_retry_after_is_ignored():
    groq = FakeSDK([rate_limit("soon"), reply()])
    client, sleeps = make_client({"groq": groq})
    client.complete("x")
    assert sleeps == [1.0]


def test_server_errors_are_retried():
    groq = FakeSDK([server_error(), reply()])
    client, _ = make_client({"groq": groq})
    assert client.complete("x").text == SECRET_ANSWER


def test_exhausted_retries_switch_to_fallback():
    groq = FakeSDK([rate_limit()] * 3)  # 1 try + 2 retries
    ollama = FakeSDK([reply("from ollama")])
    client, _ = make_client({"groq": groq, "ollama": ollama}, fallback=True)
    result = client.complete("x")
    assert groq.calls == 3
    assert (result.provider, result.model, result.text) == ("ollama", "model-o", "from ollama")


def test_fallback_disabled_raises_clear_error():
    groq = FakeSDK([rate_limit()] * 3)
    client, _ = make_client({"groq": groq}, fallback=False)
    with pytest.raises(LLMError, match="groq"):
        client.complete("x")
    assert groq.calls == 3


def test_all_providers_failing_raises():
    groq = FakeSDK([rate_limit()] * 3)
    ollama = FakeSDK([server_error()] * 3)
    client, _ = make_client({"groq": groq, "ollama": ollama}, fallback=True)
    with pytest.raises(LLMError, match="groq, ollama"):
        client.complete("x")


def test_non_retryable_error_skips_retries_and_uses_fallback():
    request = httpx.Request("POST", "https://groq.example/v1/chat/completions")
    auth = openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=request), body=None
    )
    groq = FakeSDK([auth])
    ollama = FakeSDK([reply()])
    client, sleeps = make_client({"groq": groq, "ollama": ollama}, fallback=True)
    assert client.complete("x").provider == "ollama"
    assert groq.calls == 1 and sleeps == []


def test_connection_error_without_status_is_handled():
    request = httpx.Request("POST", "https://groq.example/v1/chat/completions")
    groq = FakeSDK([openai.APIConnectionError(request=request)] * 3)
    client, _ = make_client({"groq": groq})
    with pytest.raises(LLMError):
        client.complete("x")


def timeout() -> openai.APITimeoutError:
    request = httpx.Request("POST", "https://groq.example/v1/chat/completions")
    return openai.APITimeoutError(request=request)


def test_timeout_is_not_retried_and_does_not_back_off():
    # Bug #19: a slow model stays slow, so a timeout must not be retried.
    groq = FakeSDK([timeout()] * 3)  # max_retries=2 would allow 3 attempts
    client, sleeps = make_client({"groq": groq})
    with pytest.raises(LLMError):
        client.complete("x")
    assert groq.calls == 1
    assert sleeps == []


def test_timeout_goes_straight_to_fallback():
    groq = FakeSDK([timeout()] * 3)
    ollama = FakeSDK([reply("from ollama")])
    client, sleeps = make_client({"groq": groq, "ollama": ollama}, fallback=True)
    assert client.complete("x").provider == "ollama"
    assert groq.calls == 1
    assert sleeps == []


def test_connection_error_that_is_not_a_timeout_is_still_retried():
    request = httpx.Request("POST", "https://groq.example/v1/chat/completions")
    groq = FakeSDK([openai.APIConnectionError(request=request), reply()])
    client, sleeps = make_client({"groq": groq})
    assert client.complete("x").text == SECRET_ANSWER
    assert groq.calls == 2 and sleeps == [1.0]


def test_timeout_log_contains_metadata_only(caplog):
    client, _ = make_client({"groq": FakeSDK([timeout()])})
    with caplog.at_level(logging.DEBUG), pytest.raises(LLMError):
        client.complete(SECRET_PROMPT)
    assert "provider=groq" in caplog.text and "error=APITimeoutError" in caplog.text
    assert "hunter2" not in caplog.text


def test_default_factory_builds_sdk_client_without_sdk_retries():
    sdk = LLMClient._default_factory(GROQ)
    assert sdk.max_retries == 0
    assert str(sdk.base_url).startswith("https://groq.example/v1")


def test_default_factory_uses_the_timeout_of_each_provider():
    slow = ProviderConfig("ollama", "http://localhost:11434/v1", "model-o", "ollama", 120.0)
    assert LLMClient._default_factory(GROQ).timeout == GROQ.timeout_seconds
    assert LLMClient._default_factory(slow).timeout == 120.0


def test_logs_contain_metadata_but_never_prompt_or_answer(caplog):
    groq = FakeSDK([rate_limit(), reply()])
    ollama = FakeSDK([reply()])
    client, _ = make_client({"groq": groq, "ollama": ollama}, fallback=True)
    with caplog.at_level(logging.DEBUG):
        client.complete(SECRET_PROMPT)
        failing, _ = make_client(
            {"groq": FakeSDK([server_error()] * 3), "ollama": ollama}, fallback=True
        )
        failing.complete(SECRET_PROMPT)
    logs = caplog.text
    assert "provider=groq" in logs and "429" in logs and "latency_ms" in logs
    for secret in (SECRET_PROMPT, "hunter2", "Jean Dupont", SECRET_ANSWER, "rate limited"):
        assert secret not in logs

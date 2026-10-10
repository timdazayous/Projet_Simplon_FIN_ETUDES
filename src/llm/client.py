"""OpenAI-compatible LLM client with retry, exponential backoff and optional fallback.

RGPD: only metadata is logged (provider, model, latency, tokens, error code, attempt).
Prompts, responses and exception messages are never logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

import openai
from openai import OpenAI

from src.llm.config import LLMConfig, ProviderConfig, load_config

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 60.0
# Errors worth retrying: rate limit (429), network problems, server errors (5xx).
RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,  # includes APITimeoutError
    openai.InternalServerError,
)


@dataclass(frozen=True)
class LLMResult:
    """Outcome of a successful completion."""

    text: str
    provider: str
    model: str
    latency_ms: float
    input_tokens: int
    output_tokens: int


class LLMError(RuntimeError):
    """Raised when every configured provider failed."""


def _error_code(exc: Exception) -> str:
    """Return a loggable code (HTTP status or exception class), never the message."""
    status = getattr(exc, "status_code", None)
    return str(status) if status is not None else type(exc).__name__


def _retry_after(exc: Exception) -> float | None:
    """Read the ``retry-after`` header (seconds) from an API error, if any."""
    response = getattr(exc, "response", None)
    value = response.headers.get("retry-after") if response is not None else None
    try:
        return max(float(value), 0.0) if value is not None else None
    except ValueError:
        return None


class LLMClient:
    """Single client for Groq and Ollama (both speak the OpenAI protocol)."""

    def __init__(
        self,
        config: LLMConfig | None = None,
        client_factory: Callable[[ProviderConfig], OpenAI] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or load_config()
        self._client_factory = client_factory or self._default_factory
        self._sleep = sleep
        self._clients: dict[str, OpenAI] = {}

    @staticmethod
    def _default_factory(provider: ProviderConfig) -> OpenAI:
        # max_retries=0: retries are handled here, so that they are logged and bounded.
        return OpenAI(
            base_url=provider.base_url,
            api_key=provider.api_key,
            max_retries=0,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    def _client(self, provider: ProviderConfig) -> OpenAI:
        if provider.name not in self._clients:
            self._clients[provider.name] = self._client_factory(provider)
        return self._clients[provider.name]

    def complete(self, prompt: str) -> LLMResult:
        """Send ``prompt`` to the primary provider, falling back if it keeps failing."""
        providers = [self.config.primary]
        if self.config.fallback is not None:
            providers.append(self.config.fallback)

        for index, provider in enumerate(providers):
            try:
                return self._complete_with(provider, prompt)
            except openai.APIError as exc:
                is_last = index == len(providers) - 1
                logger.warning(
                    "provider=%s model=%s failed error=%s next=%s",
                    provider.name,
                    provider.model,
                    _error_code(exc),
                    "none" if is_last else providers[index + 1].name,
                )
        raise LLMError(
            "All LLM providers failed: " + ", ".join(p.name for p in providers) + " (see logs)"
        )

    def _complete_with(self, provider: ProviderConfig, prompt: str) -> LLMResult:
        """Call one provider, retrying transient errors with capped exponential backoff."""
        client = self._client(provider)
        attempts = self.config.max_retries + 1
        for attempt in range(1, attempts + 1):
            start = time.perf_counter()
            try:
                response = client.chat.completions.create(
                    model=provider.model,
                    messages=[{"role": "user", "content": prompt}],
                )
            except RETRYABLE_ERRORS as exc:
                logger.info(
                    "provider=%s model=%s attempt=%d/%d error=%s",
                    provider.name,
                    provider.model,
                    attempt,
                    attempts,
                    _error_code(exc),
                )
                if attempt == attempts:
                    raise
                self._sleep(self._delay(attempt, _retry_after(exc)))
                continue

            usage = response.usage
            result = LLMResult(
                text=response.choices[0].message.content or "",
                provider=provider.name,
                model=provider.model,
                latency_ms=(time.perf_counter() - start) * 1000,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
            )
            logger.info(
                "provider=%s model=%s attempt=%d latency_ms=%.0f input_tokens=%d output_tokens=%d",
                result.provider,
                result.model,
                attempt,
                result.latency_ms,
                result.input_tokens,
                result.output_tokens,
            )
            return result
        raise AssertionError("unreachable")  # pragma: no cover

    def _delay(self, attempt: int, retry_after: float | None) -> float:
        """Exponential delay (base * 2^(n-1)), at least ``retry-after``, capped."""
        delay = self.config.backoff_base_seconds * 2 ** (attempt - 1)
        if retry_after is not None:
            delay = max(delay, retry_after)
        return min(delay, self.config.backoff_max_seconds)

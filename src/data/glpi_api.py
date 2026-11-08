"""Minimal client of the GLPI 11 high-level REST API (API v2, OAuth2 "password" grant).

Used by the injection of generated tickets (Issue #52, ``glpi_inject.py``). Design points:

- the secrets come from a ``.env`` file read by :func:`load_api_config`; they are never printed,
  never logged and hidden from ``repr`` (``field(repr=False)``);
- the access token lasts one hour: it is renewed before it expires (safety margin) and once
  more if the server answers 401 anyway;
- transient errors (429, 5xx, network) are retried with a growing wait; a creation (POST) is
  retried only when it certainly did not reach the server (429 or connection refused), because
  retrying a POST that may have succeeded would create a duplicate. The injection is
  idempotent anyway (it looks up ``external_id`` first), so running it again repairs the rest;
- the network, the clock and the waits are injectable, so the tests do no real call.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2
from dotenv import dotenv_values

logger = logging.getLogger("glpi_api")

REQUIRED_VARIABLES = (
    "GLPI_API_URL",
    "GLPI_OAUTH_CLIENT_ID",
    "GLPI_OAUTH_CLIENT_SECRET",
    "GLPI_API_USER",
    "GLPI_API_PASSWORD",
)
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
PAGE_SIZE = 100


class GlpiConfigError(Exception):
    """Missing or invalid configuration (the message never contains a secret value)."""


class GlpiAuthError(Exception):
    """The token request was refused (wrong client, user or password)."""


class GlpiApiError(Exception):
    """The API answered with an error that retrying will not fix (4xx other than 401/429)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status} : {message}")
        self.status = status


class GlpiUnavailable(Exception):
    """The API stayed unreachable or overloaded after all the retries."""


@dataclass(frozen=True)
class GlpiApiConfig:
    base_url: str
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    username: str = field(repr=False)
    password: str = field(repr=False)
    timeout: float = 20.0
    max_retries: int = 4
    backoff: float = 2.0
    token_margin: float = 120.0  # renew the token this many seconds before it expires


def load_api_config(env_file: str | Path = ".env") -> GlpiApiConfig:
    """Read the GLPI variables from an env file. Only variable *names* appear in errors."""
    path = Path(env_file)
    if not path.is_file():
        raise GlpiConfigError(f"fichier d'environnement introuvable : {path}")
    values = dotenv_values(path)
    missing = [name for name in REQUIRED_VARIABLES if not values.get(name)]
    if missing:
        raise GlpiConfigError(f"variables manquantes ou vides : {', '.join(missing)}")
    base_url = str(values["GLPI_API_URL"]).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise GlpiConfigError("GLPI_API_URL doit être une adresse http(s) complète")
    if parsed.scheme == "http" and parsed.hostname not in LOOPBACK_HOSTS:
        # OWASP: never send a password in clear text over a network.
        raise GlpiConfigError("GLPI_API_URL en http n'est accepté que vers la machine locale")
    return GlpiApiConfig(
        base_url=base_url,
        client_id=str(values["GLPI_OAUTH_CLIENT_ID"]),
        client_secret=str(values["GLPI_OAUTH_CLIENT_SECRET"]),
        username=str(values["GLPI_API_USER"]),
        password=str(values["GLPI_API_PASSWORD"]),
    )


class GlpiClient:
    """HTTP client with OAuth2 token handling and retries."""

    def __init__(
        self,
        config: GlpiApiConfig,
        transport: httpx2.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._http = httpx2.Client(timeout=config.timeout, transport=transport)
        self._sleep = sleep
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0
        self.token_requests = 0
        self.requests_made = 0
        self.retries = 0

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GlpiClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------ token

    def _fetch_token(self) -> None:
        cfg = self._config
        form = {
            "grant_type": "password",
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
            "username": cfg.username,
            "password": cfg.password,
            "scope": "api",
        }
        for attempt in range(cfg.max_retries + 1):
            if attempt:
                self.retries += 1
                self._sleep(cfg.backoff * 2 ** (attempt - 1))
            self.token_requests += 1
            try:
                response = self._http.post(f"{cfg.base_url}/token", data=form)
            except httpx2.TransportError:
                continue
            if response.status_code == 429 or response.status_code >= 500:
                continue
            if response.status_code != 200:
                # No response body in the message: it could echo the credentials.
                raise GlpiAuthError(f"jeton refusé (HTTP {response.status_code})")
            try:
                data = response.json()
                self._token = str(data["access_token"])
                self._expires_at = self._clock() + float(data.get("expires_in", 3600))
            except (ValueError, KeyError, TypeError) as error:
                raise GlpiAuthError("réponse de jeton inattendue") from error
            return
        raise GlpiUnavailable("serveur de jetons injoignable")

    def _bearer(self) -> str:
        if self._token is None or self._clock() >= self._expires_at - self._config.token_margin:
            self._fetch_token()
        assert self._token is not None
        return self._token

    # ------------------------------------------------------------------ requests

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx2.Response:
        """Send a request to ``{base_url}/v2{path}`` and return a successful response."""
        cfg = self._config
        url = f"{cfg.base_url}/v2{path}"
        safe_to_retry = method.upper() in ("GET", "HEAD", "PATCH")
        renewed_after_401 = False
        reason = "inconnue"
        for attempt in range(cfg.max_retries + 1):
            if attempt:
                self.retries += 1
                self._sleep(cfg.backoff * 2 ** (attempt - 1))
            all_headers = {"Authorization": f"Bearer {self._bearer()}", **(headers or {})}
            self.requests_made += 1
            try:
                response = self._http.request(
                    method, url, json=json, params=params, headers=all_headers
                )
            except httpx2.ConnectError as error:  # request never reached the server
                reason = type(error).__name__
                continue
            except httpx2.TransportError as error:  # may or may not have been processed
                if not safe_to_retry:
                    raise GlpiUnavailable(
                        f"{method} sans réponse ({type(error).__name__})"
                    ) from None
                reason = type(error).__name__
                continue
            status = response.status_code
            if status == 401 and not renewed_after_401:
                renewed_after_401 = True
                self._token = None  # expired or revoked: ask for a new one
                continue
            if status == 429:
                reason = "HTTP 429"
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    self._sleep(min(float(retry_after), 60.0))
                continue
            if status >= 500:
                if not safe_to_retry:
                    raise GlpiUnavailable(f"{method} {path} : HTTP {status}")
                reason = f"HTTP {status}"
                continue
            if status >= 400:
                raise GlpiApiError(status, _error_summary(response))
            return response
        raise GlpiUnavailable(
            f"{method} {path} : échec après {cfg.max_retries} reprises ({reason})"
        )

    def list_all(self, path: str, rsql_filter: str | None = None) -> list[dict[str, Any]]:
        """Read every page of a collection (``start`` / ``limit``)."""
        items: list[dict[str, Any]] = []
        start = 0
        while True:
            params: dict[str, Any] = {"start": start, "limit": PAGE_SIZE}
            if rsql_filter:
                params["filter"] = rsql_filter
            page = self.request("GET", path, params=params).json()
            if not isinstance(page, list):
                raise GlpiApiError(200, "liste attendue")
            items.extend(page)
            if len(page) < PAGE_SIZE:
                return items
            start += PAGE_SIZE

    def create(self, path: str, payload: dict[str, Any]) -> int:
        """POST a new item and return its identifier."""
        response = self.request("POST", path, json=payload)
        try:
            return int(response.json()["id"])
        except (ValueError, KeyError, TypeError) as error:
            raise GlpiApiError(response.status_code, "identifiant absent de la réponse") from error


def _error_summary(response: httpx2.Response) -> str:
    """Short, content-free description of an error answer (status and title only)."""
    try:
        data = response.json()
        return f"{data.get('status', '')} {data.get('title', '')}".strip() or "erreur"
    except ValueError:
        return "erreur"

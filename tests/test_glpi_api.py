"""Tests of the GLPI API v2 client (Issue #52). No real network call: MockTransport."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx2
import pytest

from src.data import glpi_api
from src.data.glpi_api import (
    GlpiApiConfig,
    GlpiApiError,
    GlpiAuthError,
    GlpiClient,
    GlpiConfigError,
    GlpiUnavailable,
)

BASE = "http://127.0.0.1:8082/api.php"
SECRET_VALUES = ("client-secret-value", "user-password-value")


class Clock:
    """Fake clock and sleep: waits are recorded instead of really happening."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def config() -> GlpiApiConfig:
    return GlpiApiConfig(
        base_url=BASE,
        client_id="client-id",
        client_secret=SECRET_VALUES[0],
        username="svc-test",
        password=SECRET_VALUES[1],
        backoff=1.0,
    )


def make_client(config: GlpiApiConfig, handler, clock: Clock | None = None):
    clock = clock or Clock()
    client = GlpiClient(
        config,
        transport=httpx2.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock.clock,
    )
    return client, clock


def token_answer(token: str = "tok-1", expires_in: int = 3600) -> httpx2.Response:
    return httpx2.Response(
        200, json={"token_type": "Bearer", "access_token": token, "expires_in": expires_in}
    )


# --------------------------------------------------------------------------- configuration


def write_env(tmp_path: Path, **overrides: str) -> Path:
    values = {
        "GLPI_API_URL": BASE,
        "GLPI_OAUTH_CLIENT_ID": "id",
        "GLPI_OAUTH_CLIENT_SECRET": "secret",
        "GLPI_API_USER": "user",
        "GLPI_API_PASSWORD": "password",
    } | overrides
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items() if v is not None), "utf-8")
    return path


def test_load_config_reads_the_env_file(tmp_path: Path) -> None:
    config = glpi_api.load_api_config(write_env(tmp_path, GLPI_API_URL=BASE + "/"))
    assert config.base_url == BASE
    assert config.username == "user"


def test_load_config_names_the_missing_variables_only(tmp_path: Path) -> None:
    path = write_env(tmp_path, GLPI_API_PASSWORD="", GLPI_OAUTH_CLIENT_SECRET="top-secret-value")
    with pytest.raises(GlpiConfigError) as error:
        glpi_api.load_api_config(path)
    assert "GLPI_API_PASSWORD" in str(error.value)
    assert "top-secret-value" not in str(error.value)


def test_load_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(GlpiConfigError, match="introuvable"):
        glpi_api.load_api_config(tmp_path / "absent.env")


def test_load_config_refuses_clear_text_http_to_a_remote_host(tmp_path: Path) -> None:
    with pytest.raises(GlpiConfigError, match="http"):
        glpi_api.load_api_config(
            write_env(tmp_path, GLPI_API_URL="http://glpi.example.org/api.php")
        )
    config = glpi_api.load_api_config(
        write_env(tmp_path, GLPI_API_URL="https://glpi.example.org/api.php")
    )
    assert config.base_url.startswith("https://")


def test_repr_hides_the_secrets(config: GlpiApiConfig) -> None:
    text = repr(config)
    assert not any(secret in text for secret in SECRET_VALUES)


# --------------------------------------------------------------------------- token


def test_token_request_uses_the_password_grant_with_api_scope(config: GlpiApiConfig) -> None:
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api.php/token":
            seen.append(parse_qs(request.content.decode()))
            return token_answer()
        return httpx2.Response(200, json=[])

    client, _ = make_client(config, handler)
    client.request("GET", "/Assistance/Ticket")
    form = seen[0]
    assert form["grant_type"] == ["password"]
    assert form["scope"] == ["api"]
    assert form["client_id"] == ["client-id"]


def test_token_is_reused_then_renewed_before_it_expires(config: GlpiApiConfig) -> None:
    tokens = iter(["tok-1", "tok-2"])
    used: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer(next(tokens), expires_in=3600)
        used.append(request.headers["Authorization"])
        return httpx2.Response(200, json=[])

    client, clock = make_client(config, handler)
    client.request("GET", "/Assistance/Ticket")
    clock.now += 1000  # still valid
    client.request("GET", "/Assistance/Ticket")
    assert client.token_requests == 1
    clock.now += 2500  # 3500 s after the first token: inside the 120 s safety margin
    client.request("GET", "/Assistance/Ticket")
    assert client.token_requests == 2
    assert used == ["Bearer tok-1", "Bearer tok-1", "Bearer tok-2"]


def test_a_401_answer_renews_the_token_once(config: GlpiApiConfig) -> None:
    tokens = iter(["tok-1", "tok-2"])
    answers = iter([401, 200])

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer(next(tokens))
        return httpx2.Response(next(answers), json=[])

    client, _ = make_client(config, handler)
    assert client.request("GET", "/Assistance/Ticket").status_code == 200
    assert client.token_requests == 2


def test_a_second_401_is_an_error_not_a_loop(config: GlpiApiConfig) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        return httpx2.Response(401, json={"status": "ERROR_UNAUTHENTICATED", "title": "no"})

    client, _ = make_client(config, handler)
    with pytest.raises(GlpiApiError) as error:
        client.request("GET", "/Assistance/Ticket")
    assert error.value.status == 401


def test_refused_credentials_raise_without_echoing_them(config: GlpiApiConfig) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"error": "invalid_client", "hint": SECRET_VALUES[0]})

    client, clock = make_client(config, handler)
    with pytest.raises(GlpiAuthError) as error:
        client.request("GET", "/Assistance/Ticket")
    assert SECRET_VALUES[0] not in str(error.value)
    assert clock.sleeps == []  # no retry on a refusal: it would only lock the account


def test_token_server_error_is_retried_then_gives_up(config: GlpiApiConfig) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503)

    client, clock = make_client(config, handler)
    with pytest.raises(GlpiUnavailable):
        client.request("GET", "/Assistance/Ticket")
    assert clock.sleeps == [1.0, 2.0, 4.0, 8.0]


# --------------------------------------------------------------------------- retries


def test_get_is_retried_with_growing_waits_on_5xx_and_429(config: GlpiApiConfig) -> None:
    answers = iter([500, 429, 200])

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        return httpx2.Response(next(answers), json=[])

    client, clock = make_client(config, handler)
    assert client.request("GET", "/Assistance/Ticket").status_code == 200
    assert clock.sleeps == [1.0, 2.0]
    assert client.retries == 2


def test_retry_after_header_is_honoured(config: GlpiApiConfig) -> None:
    answers = iter(
        [httpx2.Response(429, headers={"Retry-After": "7"}), httpx2.Response(200, json=[])]
    )

    def handler(request: httpx2.Request) -> httpx2.Response:
        return token_answer() if request.url.path.endswith("/token") else next(answers)

    client, clock = make_client(config, handler)
    client.request("GET", "/Assistance/Ticket")
    assert 7.0 in clock.sleeps


def test_post_is_not_retried_after_a_server_error(config: GlpiApiConfig) -> None:
    """A POST that may have been processed must not be repeated (duplicate ticket)."""
    posts: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        posts.append(1)
        return httpx2.Response(500)

    client, _ = make_client(config, handler)
    with pytest.raises(GlpiUnavailable):
        client.create("/Assistance/Ticket", {"name": "x"})
    assert len(posts) == 1


def test_post_is_not_retried_after_a_timeout_but_is_after_a_refused_connection(
    config: GlpiApiConfig,
) -> None:
    errors = iter([httpx2.ConnectError("refused"), httpx2.ReadTimeout("slow")])

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        raise next(errors)

    client, _ = make_client(config, handler)
    with pytest.raises(GlpiUnavailable):
        client.create("/Assistance/Ticket", {"name": "x"})
    assert client.retries == 1  # refused connection retried once, timeout not retried


def test_client_error_is_raised_with_status_and_no_body(config: GlpiApiConfig) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        return httpx2.Response(
            403,
            json={"status": "ERROR_RIGHT_MISSING", "title": "No permission", "detail": "secret"},
        )

    client, _ = make_client(config, handler)
    with pytest.raises(GlpiApiError) as error:
        client.request("GET", "/Administration/Entity")
    assert error.value.status == 403
    assert "ERROR_RIGHT_MISSING" in str(error.value)
    assert "secret" not in str(error.value)


# --------------------------------------------------------------------------- helpers


def test_list_all_reads_every_page(config: GlpiApiConfig) -> None:
    total = 250
    starts: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        query = parse_qs(request.url.query.decode())
        start, limit = int(query["start"][0]), int(query["limit"][0])
        starts.append(start)
        return httpx2.Response(
            206, json=[{"id": i} for i in range(start, min(start + limit, total))]
        )

    client, _ = make_client(config, handler)
    items = client.list_all("/Assistance/Ticket", "external_id=like=GEN-T-*")
    assert len(items) == total
    assert starts == [0, 100, 200]


def test_create_returns_the_new_identifier(config: GlpiApiConfig) -> None:
    bodies: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/token"):
            return token_answer()
        bodies.append(json.loads(request.content))
        return httpx2.Response(201, json={"id": 42, "href": "/Assistance/Ticket/42"})

    client, _ = make_client(config, handler)
    assert client.create("/Assistance/Ticket", {"name": "x"}) == 42
    assert bodies == [{"name": "x"}]


def test_create_without_identifier_is_an_error(config: GlpiApiConfig) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return (
            token_answer() if request.url.path.endswith("/token") else httpx2.Response(201, json={})
        )

    client, _ = make_client(config, handler)
    with pytest.raises(GlpiApiError, match="identifiant"):
        client.create("/Assistance/Ticket", {})

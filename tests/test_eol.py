"""Tests of the endoflife.date extraction (Issue #41). No real network call: MockTransport."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx2
import pytest

from src.data import eol

TODAY = date(2026, 10, 23)


def api_answer(name: str = "ubuntu", releases: list[dict] | None = None) -> dict:
    if releases is None:
        releases = [
            {
                "name": "26.04",
                "codename": "Resolute Raccoon",
                "label": "26.04 (LTS)",
                "releaseDate": "2026-04-23",
                "isLts": True,
                "eoasFrom": "2031-05-29",
                "eolFrom": "2031-05-29",
                "eoesFrom": "2036-04-23",
                "isMaintained": True,
                "latest": {"name": "26.04.1", "date": "2026-08-27"},
            },
            {
                "name": "24.10",
                "codename": None,
                "label": "24.10",
                "releaseDate": "2024-10-10",
                "isLts": False,
                "eoasFrom": None,
                "eolFrom": "2025-07-10",
                "eoesFrom": None,
                "isMaintained": False,
                "latest": None,
            },
        ]
    return {"result": {"name": name, "label": name.title(), "category": "os", "releases": releases}}


@pytest.fixture
def config(tmp_path: Path) -> eol.EolConfig:
    base = eol.load_config()
    return replace(
        base,
        output_directory=tmp_path / "eol",
        cache_directory=tmp_path / "eol" / "cache",
        products=("ubuntu", "php", "ghost"),
    )


class Recorder:
    """Fake clock and sleep: waits are recorded instead of really happening."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_client(config: eol.EolConfig, handler, recorder: Recorder | None = None):
    recorder = recorder or Recorder()
    client = eol.EolClient(
        config,
        transport=httpx2.MockTransport(handler),
        sleep=recorder.sleep,
        clock=recorder.clock,
    )
    return client, recorder


# --------------------------------------------------------------------------- configuration


def test_real_configuration_is_valid() -> None:
    config = eol.load_config()
    assert "windows-server" in config.products and "postgresql" in config.products
    assert config.min_interval >= 1.0
    assert config.base_url.startswith("https://endoflife.date/api/v1/")
    assert "Simplon" in config.user_agent


def test_configuration_rejects_duplicates_and_fast_rate(tmp_path: Path) -> None:
    raw = (eol.DEFAULT_CONFIG_PATH).read_text(encoding="utf-8")
    duplicate = tmp_path / "dup.yaml"
    duplicate.write_text(raw.replace("  - php\n", "  - python\n"), encoding="utf-8")
    with pytest.raises(ValueError, match="doublons"):
        eol.load_config(duplicate)
    fast = tmp_path / "fast.yaml"
    fast.write_text(
        raw.replace("min_interval_seconds: 1.0", "min_interval_seconds: 0.1"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="min_interval_seconds"):
        eol.load_config(fast)


# --------------------------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2031-05-29", "2031-05-29"),
        ("2031-05-29T10:00:00Z", "2031-05-29"),
        (None, None),
        (True, None),
        ("", None),
        ("bientôt", None),
    ],
)
def test_normalize_date(value, expected) -> None:
    assert eol.normalize_date(value) == expected


def test_normalize_product_name() -> None:
    assert eol.normalize_product_name("  Windows-Server ") == "windows-server"


def test_parse_product_one_row_per_version() -> None:
    rows, invalid = eol.parse_product(api_answer(), "2026-10-23")
    assert invalid == 0
    assert [r["version"] for r in rows] == ["26.04", "24.10"]
    first, second = rows
    assert first["product"] == "ubuntu"
    assert first["security_support_end"] == "2031-05-29"
    assert first["extended_support_end"] == "2036-04-23"
    assert first["is_lts"] is True and first["is_maintained"] is True
    assert first["latest_version"] == "26.04.1"
    assert second["active_support_end"] is None
    assert second["is_maintained"] is False
    assert second["latest_version"] is None
    assert first["extracted_at"] == "2026-10-23" and first["source"] == "endoflife.date"


def test_parse_product_counts_invalid_dates_and_falls_back_on_is_eol() -> None:
    release = {"name": 7, "releaseDate": "n/a", "eolFrom": "2020-01-01", "isEol": True}
    rows, invalid = eol.parse_product(api_answer(releases=[release]), "2026-10-23")
    assert invalid == 1
    assert rows[0]["release_date"] is None
    assert rows[0]["version"] == "7"
    assert rows[0]["is_maintained"] is False


# --------------------------------------------------------------------------- HTTP client


def test_fetch_product_sends_user_agent_and_returns_json(config) -> None:
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["ua"] = request.headers["user-agent"]
        return httpx2.Response(200, json=api_answer())

    client, _ = make_client(config, handler)
    data = client.fetch_product("ubuntu")
    assert data["result"]["name"] == "ubuntu"
    assert seen["url"] == "https://endoflife.date/api/v1/products/ubuntu/"
    assert seen["ua"] == config.user_agent


def test_404_raises_product_not_found_without_retry(config) -> None:
    client, recorder = make_client(config, lambda r: httpx2.Response(404, text="<html>404</html>"))
    with pytest.raises(eol.ProductNotFound):
        client.fetch_product("ghost")
    assert client.requests_made == 1 and recorder.sleeps == []


def test_server_errors_are_retried_with_growing_waits(config) -> None:
    answers = iter([503, 500, 429, 200])

    def handler(request: httpx2.Request) -> httpx2.Response:
        status = next(answers)
        return httpx2.Response(status, json=api_answer() if status == 200 else {})

    client, recorder = make_client(config, handler)
    assert client.fetch_product("ubuntu")["result"]["name"] == "ubuntu"
    assert client.requests_made == 4 and client.retries == 3
    # backoff 2 s, 4 s, 8 s (each already above the 1 s rate limit, so no extra wait)
    assert recorder.sleeps == [2.0, 4.0, 8.0]


def test_retries_exhausted_raises_fetch_error(config) -> None:
    client, _ = make_client(config, lambda r: httpx2.Response(502))
    with pytest.raises(eol.FetchError, match="HTTP 502"):
        client.fetch_product("ubuntu")
    assert client.requests_made == config.max_retries + 1


def test_timeout_is_retried(config) -> None:
    calls = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx2.ConnectTimeout("délai dépassé", request=request)
        return httpx2.Response(200, json=api_answer())

    client, _ = make_client(config, handler)
    assert client.fetch_product("ubuntu")["result"]["name"] == "ubuntu"
    assert client.retries == 1


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(403, text="interdit"),
        httpx2.Response(200, text="pas du JSON"),
        httpx2.Response(200, json={"autre": 1}),
        httpx2.Response(200, json=[1, 2]),
    ],
)
def test_unexpected_answers_raise_fetch_error_without_retry(config, response) -> None:
    client, _ = make_client(config, lambda r: response)
    with pytest.raises(eol.FetchError):
        client.fetch_product("ubuntu")
    assert client.requests_made == 1


def test_rate_limit_one_request_per_second(config) -> None:
    client, recorder = make_client(config, lambda r: httpx2.Response(200, json=api_answer()))
    for _ in range(3):
        client.fetch_product("ubuntu")
    # the fake clock only moves when sleeping: each of the 2 next calls waits the full interval
    assert recorder.sleeps == [config.min_interval, config.min_interval]


def test_rate_limit_does_not_wait_when_enough_time_passed(config) -> None:
    client, recorder = make_client(config, lambda r: httpx2.Response(200, json=api_answer()))
    client.fetch_product("ubuntu")
    recorder.now += 5
    client.fetch_product("ubuntu")
    assert recorder.sleeps == []


# --------------------------------------------------------------------------- whole run


def run_handler(request: httpx2.Request) -> httpx2.Response:
    product = request.url.path.rstrip("/").rsplit("/", 1)[-1]
    if product == "ghost":
        return httpx2.Response(404, text="<html>404</html>")
    return httpx2.Response(200, json=api_answer(product))


def test_run_extraction_writes_jsonl_and_report(config) -> None:
    client, _ = make_client(config, run_handler)
    report = eol.run_extraction(config, client=client, today=TODAY)
    assert report.products_ok == 2 and report.not_found == ["ghost"] and report.failed == []
    assert report.versions == 4 and report.requests == 3
    assert report.exit_code() == eol.EXIT_PARTIAL
    lines = (config.output_directory / "products.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert len(rows) == 4 and {r["product"] for r in rows} == {"ubuntu", "php"}
    saved = json.loads((config.output_directory / "report.json").read_text(encoding="utf-8"))
    assert saved["versions"] == 4 and saved["not_found"] == ["ghost"]


def test_same_day_cache_avoids_new_requests(config) -> None:
    client, _ = make_client(config, run_handler)
    eol.run_extraction(config, client=client, today=TODAY)
    client2, _ = make_client(config, lambda r: pytest.fail("appel réseau inattendu"))
    # ghost (404) is not cached: only it would be requested, so restrict to cached products
    report = eol.run_extraction(config, only=["ubuntu", "php"], client=client2, today=TODAY)
    assert report.from_cache == 2 and report.requests == 0 and report.exit_code() == eol.EXIT_OK


def test_cache_of_another_day_is_ignored_and_corrupted_cache_refetched(config) -> None:
    client, _ = make_client(config, run_handler)
    eol.run_extraction(config, only=["ubuntu"], client=client, today=TODAY)
    client2, _ = make_client(config, run_handler)
    report = eol.run_extraction(config, only=["ubuntu"], client=client2, today=date(2026, 10, 30))
    assert report.from_cache == 0 and report.requests == 1
    (config.cache_directory / "ubuntu-2026-10-30.json").write_text("{pas du json", encoding="utf-8")
    client3, _ = make_client(config, run_handler)
    report = eol.run_extraction(config, only=["ubuntu"], client=client3, today=date(2026, 10, 30))
    assert report.from_cache == 0 and report.requests == 1


def test_unreachable_source_keeps_previous_file_and_exit_code_3(config) -> None:
    client, _ = make_client(config, run_handler)
    eol.run_extraction(config, only=["ubuntu"], client=client, today=TODAY)
    output = config.output_directory / "products.jsonl"
    before = output.read_text(encoding="utf-8")

    down, _ = make_client(config, lambda r: httpx2.Response(503))
    report = eol.run_extraction(config, only=["php"], client=down, today=TODAY)
    assert report.products_ok == 0 and report.failed == ["php"]
    assert report.exit_code() == eol.EXIT_NOTHING
    assert output.read_text(encoding="utf-8") == before


def test_run_extraction_creates_its_own_client_when_cache_is_complete(config) -> None:
    client, _ = make_client(config, run_handler)
    eol.run_extraction(config, only=["ubuntu"], client=client, today=TODAY)
    report = eol.run_extraction(config, only=["ubuntu"], today=TODAY)  # cache only, real client
    assert report.from_cache == 1 and report.requests == 0

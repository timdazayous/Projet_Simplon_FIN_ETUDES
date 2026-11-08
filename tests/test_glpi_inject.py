"""Tests of the injection of generated tickets into GLPI (Issue #52). Fake GLPI in memory."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import httpx2
import pytest

from src.data import glpi_inject
from src.data.glpi_api import GlpiApiConfig, GlpiClient
from src.data.glpi_inject import run_injection

BASE = "http://127.0.0.1:8082/api.php"
POOL = 12


class FakeGlpi:
    """Just enough of the GLPI API v2: token, categories, entities and tickets."""

    def __init__(self) -> None:
        self.categories: list[dict[str, Any]] = []
        self.entities: list[dict[str, Any]] = [{"id": 0, "name": "Root entity"}]
        self.tickets: list[dict[str, Any]] = []
        self.keep_entity_name = True
        self.fail_ticket_status: int | None = None
        self.forbid_categories = False
        self.posts: list[str] = []

    def collection(self, path: str) -> list[dict[str, Any]]:
        return {
            "/Dropdowns/ITILCategory": self.categories,
            "/Administration/Entity": self.entities,
            "/Assistance/Ticket": self.tickets,
        }[path]

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path.removeprefix("/api.php")
        if path == "/token":
            return httpx2.Response(200, json={"access_token": "t", "expires_in": 3600})
        path = path.removeprefix("/v2")
        match = re.fullmatch(r"(/Administration/Entity)/(\d+)", path)
        if request.method == "GET" and match:
            found = [e for e in self.entities if e["id"] == int(match[2])]
            return httpx2.Response(200, json=found[0])
        items = self.collection(path)
        if request.method == "GET":
            query = parse_qs(request.url.query.decode())
            start, limit = int(query["start"][0]), int(query["limit"][0])
            rows = items
            if "filter" in query:  # external_id=like=GEN-T-*
                rows = [r for r in items if str(r.get("external_id", "")).startswith("GEN-T-")]
            return httpx2.Response(200, json=rows[start : start + limit])
        # POST
        self.posts.append(path)
        body = json.loads(request.content)
        if path == "/Dropdowns/ITILCategory" and self.forbid_categories:
            return httpx2.Response(403, json={"status": "ERROR_RIGHT_MISSING", "title": "no"})
        if path == "/Assistance/Ticket" and self.fail_ticket_status:
            return httpx2.Response(self.fail_ticket_status, json={"status": "ERROR", "title": "x"})
        row = {"id": len(items) + (1 if path != "/Administration/Entity" else 0), **body}
        if path == "/Administration/Entity" and not self.keep_entity_name:
            row.pop("name")
        items.append(row)
        return httpx2.Response(201, json={"id": row["id"]})


@pytest.fixture
def fake() -> FakeGlpi:
    return FakeGlpi()


@pytest.fixture
def client(fake: FakeGlpi) -> GlpiClient:
    config = GlpiApiConfig(BASE, "id", "secret", "user", "password", backoff=0.0)
    return GlpiClient(config, transport=httpx2.MockTransport(fake.handler), sleep=lambda s: None)


def inject(client: GlpiClient, tmp_path: Path, **kwargs: Any):
    options = {"seed": 7, "pool": POOL, "count": POOL, "report_path": tmp_path / "report.json"}
    return run_injection(client, **(options | kwargs))


# --------------------------------------------------------------------------- conversion


def test_priority_and_type_mapping_follows_the_taxonomy_documentation() -> None:
    assert glpi_inject.PRIORITY_TO_GLPI == {"P1": 5, "P2": 4, "P3": 3, "P4": 2}
    assert glpi_inject.TYPE_TO_GLPI == {"incident": 1, "service_request": 2, "information": 2}


def test_text_is_escaped_and_split_in_paragraphs() -> None:
    result = glpi_inject.text_to_html("Bonjour,\n\nPrix < 5 & <b>gras</b>\nligne 2")
    assert result == "<p>Bonjour,</p><p>Prix &lt; 5 &amp; &lt;b&gt;gras&lt;/b&gt;<br>ligne 2</p>"


def test_dates_are_sent_in_utc_with_an_offset() -> None:
    assert glpi_inject.to_glpi_datetime("2026-01-05T21:32:09") == "2026-01-05T21:32:09+00:00"
    assert glpi_inject.to_glpi_datetime("2026-01-05T22:32:09+01:00") == "2026-01-05T21:32:09+00:00"


# --------------------------------------------------------------------------- run


def test_first_run_creates_categories_entities_and_tickets(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    report = inject(client, tmp_path)
    assert report.exit_code() == glpi_inject.EXIT_OK
    assert report.categories_created == 12
    assert report.tickets_created == POOL == len(fake.tickets)
    assert {c["code"] for c in fake.categories} >= {"network", "backup"}
    ticket = fake.tickets[0]
    assert re.fullmatch(r"GEN-T-\d{6}", ticket["external_id"])  # traceability
    assert ticket["priority"] == ticket["urgency"] == ticket["impact"]
    assert ticket["date"] == ticket["date_creation"]
    assert ticket["date"].endswith("+00:00")
    assert json.loads((tmp_path / "report.json").read_text("utf-8"))["tickets_created"] == POOL


def test_second_run_creates_nothing(client: GlpiClient, fake: FakeGlpi, tmp_path: Path) -> None:
    inject(client, tmp_path)
    posts_after_first = len(fake.posts)
    report = inject(client, tmp_path)
    assert len(fake.posts) == posts_after_first
    assert report.tickets_created == 0
    assert report.tickets_already_present == POOL
    assert report.categories_created == report.entities_created == 0
    assert len(fake.tickets) == POOL


def test_a_smaller_count_then_the_full_series_adds_only_the_difference(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    inject(client, tmp_path, count=4)
    report = inject(client, tmp_path)
    assert report.tickets_already_present == 4
    assert report.tickets_created == POOL - 4
    assert len({t["external_id"] for t in fake.tickets}) == POOL


def test_dry_run_reads_but_creates_nothing(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    report = inject(client, tmp_path, dry_run=True)
    assert fake.posts == []
    assert report.tickets_created == POOL  # "would create"
    assert report.dry_run
    assert not (tmp_path / "report.json").exists()


def test_without_entities_every_ticket_goes_to_the_root_entity(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    report = inject(client, tmp_path, use_entities=False)
    assert report.entities_created == 0
    assert {t["entity"]["id"] for t in fake.tickets} == {0}


def test_entity_whose_name_is_dropped_stops_the_run(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    fake.keep_entity_name = False
    report = inject(client, tmp_path)
    assert report.entity_name_lost
    assert report.exit_code() == glpi_inject.EXIT_ENTITY
    assert len([p for p in fake.posts if p == "/Administration/Entity"]) == 1  # no avalanche
    assert fake.tickets == []


def test_missing_right_is_reported_with_its_own_exit_code(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    fake.forbid_categories = True
    report = inject(client, tmp_path)
    assert report.forbidden
    assert report.exit_code() == glpi_inject.EXIT_PERMISSION


def test_a_rejected_ticket_is_counted_and_the_run_goes_on(
    client: GlpiClient, fake: FakeGlpi, tmp_path: Path
) -> None:
    fake.fail_ticket_status = 400
    report = inject(client, tmp_path)
    assert report.tickets_failed == POOL
    assert report.failure_reasons == {"HTTP 400": POOL}
    assert report.exit_code() == glpi_inject.EXIT_PARTIAL


def test_the_report_holds_counters_only(client: GlpiClient, fake: FakeGlpi, tmp_path: Path) -> None:
    inject(client, tmp_path)
    text = (tmp_path / "report.json").read_text("utf-8")
    assert fake.tickets[0]["name"] not in text
    assert "secret" not in text and "password" not in text

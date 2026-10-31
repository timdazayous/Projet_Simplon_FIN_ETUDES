"""Tests of the Windows known issues scraper (Issue #45). No network call.

Microsoft Learn terms of use forbid copying its content: every page below is FICTITIOUS HTML built
by ``build_page``. Titles, KB numbers, builds and texts are invented; only the tag structure
(summary table, detail blocks, history table, platform list) imitates the real pages.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest

from src.data.certfr import ConfigError, FetchError, RobotsError
from src.data.windows_issues import (
    Fetcher,
    PageFormatError,
    RobotsRules,
    TrackedPage,
    WindowsIssuesConfig,
    load_config,
    normalize_status,
    pacific_to_utc,
    parse_page,
    parse_pt_datetime,
    parse_summary_row,
    read_records,
    run_extraction,
)

BASE = "https://learn.example.test"
PAGE = TrackedPage("fictive-a", "Windows Fictif A", "/fr-fr/release-health/status-fictive-a")
PAGE_URL = BASE + PAGE.path
ROBOTS = "User-agent: *\nDisallow: /*/search/?*terms\nDisallow: /api/private/*\n"
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- fictitious pages


def issue_html(
    issue_id: str,
    title: str,
    status: str,
    *,
    resolving_kb: str | None = None,
    origin: str = "Build du système d'exploitation 99999.1 <br/> <a>KB9000001</a><br/>2026-01-02",
    updated: str = "2026-07-01 <br/>10:13 PT",
    history: str = "Ouvert : 2026-06-01, 09:00 PT",
    platforms_in_div: bool = False,
    platforms: str | None = "Client : Windows Fictif A ; Windows Fictif B</li><li>Serveur : aucun",
) -> tuple[str, str]:
    """(row of the summary table, detail block) of one fictitious issue."""
    kb = f"<br/> <a>{resolving_kb}</a>" if resolving_kb else "<br/> "
    row = (
        f'<tr><td><div id="{issue_id}msg"></div><a href="#{issue_id}msgdesc"><b>{title}</b></a>'
        f"<br/>Résumé inventé du problème {issue_id}.<br/></td>"
        f'<td class="has-no-wrap">{origin}</td><td>{status}{kb}</td><td>{updated}</td></tr>'
    )
    platform_html = (
        f'<p><strong>Plateformes affectées :</strong></p><ul><li class="x">{platforms}</li></ul>'
        if platforms is not None
        else ""
    )
    body = f"<p>Texte inventé.</p>{platform_html}"
    if platforms_in_div:
        body = f'<p>Texte inventé.</p><div class="ql-indent-1">{platform_html}</div>'
    detail = (
        f'<div id="{issue_id}msgdesc"></div><h4><p>{title}</p></h4><p></p>'
        "<table><tbody><tr><th>Statut</th><th>Mise à jour d'origine</th><th>Historique</th></tr>"
        f"<tr><td>{status}</td><td>origine</td><td>{history}</td></tr></tbody></table>{body}"
    )
    return row, detail


def build_page(issues: list[tuple[str, str]] | None = None, *, h1=True, section=True) -> str:
    issues = (
        [
            issue_html(
                "9001",
                "Problème fictif numéro un",
                "Résolu",
                resolving_kb="KB9000002",
                history="Résolu : 2026-07-01, 10:00 PT<br/>Ouvert : 2026-06-01, 09:00 PT",
            ),
            issue_html(
                "9002",
                "Problème fictif numéro deux",
                "Atténué : externe",
                origin="Non applicable <br/> <br/>",
                updated="2026-12-05 <br/>17h44 PT",
                history="Atténué : 2026-12-05, 17:00 PT<br/>Ouvert : 2026-12-01, 08:30 PT",
                platforms_in_div=True,
            ),
            issue_html(
                "9003",
                "Problème fictif numéro trois",
                "Confirmé",
                platforms="Client : aucun</li><li>Serveur : Windows Fictif C",
            ),
        ]
        if issues is None
        else issues
    )
    rows = "".join(r for r, _ in issues)
    details = "".join(d for _, d in issues)
    table = (
        "<table><thead><tr><th>Résumé</th><th>Mise à jour d'origine</th><th>Statut</th>"
        f"<th>Dernière mise à jour</th></tr></thead><tbody>{rows}</tbody></table>"
        if rows
        else ""
    )
    return (
        "<html><body><main><div class='content'>"
        + ("<h1>Page fictive</h1>" if h1 else "")
        + "<div class='content'>"
        + ("<h2 id='x'>Problèmes connus</h2>" if section else "<h2>Autre</h2>")
        + f"{table}<h2>Détails du problème</h2><h3>Juillet 2026</h3>{details}"
        "</div></main></body></html>"
    )


def parse(html: str):
    return parse_page(html, PAGE, PAGE_URL, "2026-10-31T12:00:00+00:00")


# --------------------------------------------------------------------------- parsing


def test_parse_page_extracts_every_field():
    records = parse(build_page())
    assert [r["issue_id"] for r in records] == ["9001", "9002", "9003"]
    first = records[0]
    assert first["id"] == "fictive-a:9001"
    assert first["windows_version"] == "Windows Fictif A"
    assert first["title"] == "Problème fictif numéro un"
    assert first["summary"] == "Résumé inventé du problème 9001."
    assert first["status"] == "resolved"
    assert first["status_raw"] == "Résolu"
    assert first["originating_build"] == "99999.1"
    assert first["originating_kb"] == "KB9000001"
    assert first["originating_date"] == "2026-01-02"
    assert first["resolving_kb"] == "KB9000002"
    assert first["last_updated_at"] == "2026-07-01T17:13:00Z"  # 10:13 PDT = 17:13 UTC
    assert first["published_at"] == "2026-06-01T16:00:00Z"
    assert [h["status_raw"] for h in first["history"]] == ["Résolu", "Ouvert"]
    assert first["platforms"] == {
        "client": ["Windows Fictif A", "Windows Fictif B"],
        "server": [],
    }
    assert first["url"] == f"{PAGE_URL}#9001msgdesc"
    assert first["page_url"] == PAGE_URL


def test_not_applicable_origin_and_winter_time_and_nested_platforms():
    second = parse(build_page())[1]
    assert second["status"] == "mitigated" and second["status_external"] is True
    assert second["originating_build"] is None
    assert second["originating_kb"] is None and second["originating_date"] is None
    assert second["last_updated_at"] == "2026-12-06T01:44:00Z"  # 17h44 PST = 01:44 UTC next day
    # The platform list sits in an indented ``div`` on this one.
    assert second["platforms"]["client"] == ["Windows Fictif A", "Windows Fictif B"]


def test_open_issue_and_missing_platform_list():
    row, detail = issue_html("9010", "Autre problème fictif", "Confirmé", platforms=None)
    record = parse(build_page([(row, detail)]))[0]
    assert record["status"] == "open" and record["resolving_kb"] is None
    assert record["platforms"] is None  # absent on the page: left empty, not invented


def test_page_without_known_issue_gives_no_record():
    assert parse(build_page([])) == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Résolu", ("resolved", False)),
        ("Résolu : externe", ("resolved", True)),
        ("Atténué", ("mitigated", False)),
        ("Atténué : externe", ("mitigated", True)),
        ("Confirmé", ("open", False)),
        ("Enquête en cours", ("open", False)),
        ("Signalé", ("open", False)),
        ("Ouvert", ("open", False)),
    ],
)
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_unknown_status_is_an_explicit_error():
    with pytest.raises(PageFormatError, match="Statut inconnu"):
        normalize_status("Mystérieux")


def test_pacific_time_to_utc_around_the_daylight_saving_changes():
    assert (
        pacific_to_utc(datetime(2026, 3, 8, 1, 59)).isoformat() == "2026-03-08T09:59:00+00:00"
    )  # PST
    assert (
        pacific_to_utc(datetime(2026, 3, 8, 3, 0)).isoformat() == "2026-03-08T10:00:00+00:00"
    )  # PDT
    assert pacific_to_utc(datetime(2026, 11, 1, 0, 59)).isoformat() == "2026-11-01T07:59:00+00:00"
    assert (
        pacific_to_utc(datetime(2026, 11, 1, 2, 0)).isoformat() == "2026-11-01T10:00:00+00:00"
    )  # PST
    assert pacific_to_utc(datetime(2026, 7, 1, 12, 0)).isoformat() == "2026-07-01T19:00:00+00:00"


def test_ambiguous_autumn_hour_keeps_the_first_occurrence():
    # 01:30 happens twice on 2026-11-01; fold=0 (default) is the first one, still PDT (UTC-7).
    assert pacific_to_utc(datetime(2026, 11, 1, 1, 30)).isoformat() == "2026-11-01T08:30:00+00:00"


def test_both_date_time_formats_and_bad_ones():
    assert parse_pt_datetime("2026-07-01 10:13 PT") == "2026-07-01T17:13:00Z"
    assert parse_pt_datetime("2026-07-01 17h44 PT") == "2026-07-02T00:44:00Z"
    for bad in ("hier", "2026-07-01", "2026-13-01 10:00 PT"):
        with pytest.raises(PageFormatError):
            parse_pt_datetime(bad)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda h: h.replace("<h1>Page fictive</h1>", ""),
        lambda h: h.replace("Problèmes connus", "Autre section"),
        lambda h: h.replace("<th>Statut</th><th>Dernière", "<th>Etat</th><th>Dernière"),  # no table
        lambda h: h.replace('<div id="9001msgdesc"></div>', ""),  # row without its detail block
        lambda h: h.replace('href="#9001msgdesc"', 'href="#autre"'),  # row without detail link
        lambda h: h.replace("<td>Confirmé", "<td>Mystérieux"),  # unknown status
        lambda h: h.replace("2026-07-01 <br/>10:13 PT", "plus tard", 1),  # unreadable date
        lambda h: h.replace("Ouvert : 2026-06-01, 09:00 PT", "pas de date"),  # unreadable history
        lambda h: h.replace("<td>Confirmé<br/> </td>", "", 1),  # row with 3 columns
        lambda h: h.replace(
            "Build du système d'exploitation 99999.1 <br/> <a>KB9000001</a><br/>2026-01-02",
            "contenu incompréhensible",
            1,
        ),
    ],
)
def test_unexpected_structure_raises_instead_of_producing_empty_fields(mutate):
    with pytest.raises(PageFormatError):
        parse(mutate(build_page()))


def test_detail_without_summary_row_is_refused():
    extra = '<div id="9999msgdesc"></div><h4><p>Orphelin fictif</p></h4>'
    html = build_page().replace("</div></main>", extra + "</div></main>")
    with pytest.raises(PageFormatError, match="sans ligne récapitulative"):
        parse(html)


def test_details_without_summary_table_are_refused():
    row, detail = issue_html("9020", "Fictif", "Résolu")
    html = build_page([(row, detail)]).replace("<th>Résumé</th>", "<th>Autre</th>")
    with pytest.raises(PageFormatError, match="tableau récapitulatif absent"):
        parse(html)


def test_duplicate_issue_in_the_table_is_refused():
    pair = issue_html("9030", "Fictif", "Résolu")
    with pytest.raises(PageFormatError, match="en double"):
        parse(build_page([pair, pair]))


def test_summary_row_helper_rejects_a_row_without_cells():
    from bs4 import BeautifulSoup

    row = BeautifulSoup("<table><tr><td>a</td></tr></table>", "html.parser").find("tr")
    with pytest.raises(PageFormatError, match="colonnes"):
        parse_summary_row(row)


# --------------------------------------------------------------------------- robots.txt


def test_robots_rules_understand_wildcards_allow_and_dollar():
    rules = RobotsRules(
        "User-agent: *\nDisallow: /*/search/?*terms\nDisallow: /api/*\nAllow: /api/open/*\n"
        "Disallow: /*.pdf$\nDisallow:\n",
        "projet-test/0.1 (https://github.com/x/y)",
    )
    assert rules.can_fetch(f"{BASE}/fr-fr/windows/release-health/status-x")
    assert not rules.can_fetch(f"{BASE}/fr-fr/search/?terms=x")
    assert rules.can_fetch(f"{BASE}/fr-fr/search/")
    assert not rules.can_fetch(f"{BASE}/api/attachments/1")
    assert rules.can_fetch(f"{BASE}/api/open/1")  # the longer Allow wins
    assert not rules.can_fetch(f"{BASE}/doc.pdf")
    assert rules.can_fetch(f"{BASE}/doc.pdf.html")


def test_robots_rules_prefer_the_group_naming_the_agent():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: projet-test\nAllow: /\n"
    assert RobotsRules(text, "projet-test/0.1").can_fetch(f"{BASE}/x")
    assert not RobotsRules(text, "autre/1.0").can_fetch(f"{BASE}/x")


# --------------------------------------------------------------------------- configuration


def make_config(tmp_path: Path, **overrides) -> WindowsIssuesConfig:
    values = {
        "base_url": BASE,
        "user_agent": "test-agent/0.1 (https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES)",
        "min_interval_seconds": 2.0,
        "timeout_seconds": 5,
        "max_retries": 1,
        "backoff_seconds": 1.0,
        "max_consecutive_failures": 3,
        "output_directory": tmp_path / "out",
        "pages": (
            PAGE,
            TrackedPage("fictive-b", "Windows Fictif B", "/fr-fr/release-health/status-fictive-b"),
        ),
    }
    values.update(overrides)
    return WindowsIssuesConfig(**values)


def test_shipped_config_is_valid_and_respects_the_rules():
    config = load_config()
    assert config.min_interval_seconds >= 2.0
    assert "github.com" in config.user_agent
    assert len(config.pages) == 7
    assert all(p.path.startswith("/fr-fr/windows/release-health/") for p in config.pages)


def write_yaml(tmp_path: Path, **overrides) -> Path:
    import yaml

    values = {
        "base_url": BASE,
        "user_agent": "t/1 (https://github.com/x/y)",
        "min_interval_seconds": 2.0,
        "timeout_seconds": 5,
        "max_retries": 1,
        "backoff_seconds": 1.0,
        "max_consecutive_failures": 3,
        "output_directory": str(tmp_path),
        "pages": [{"slug": "a", "label": "A", "path": "/a"}],
    }
    values.update(overrides)
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    return path


def test_config_from_yaml(tmp_path):
    assert load_config(write_yaml(tmp_path)).pages[0].slug == "a"


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_interval_seconds": 1.0},
        {"user_agent": "anonyme"},
        {"pages": []},
        {"pages": [{"slug": "a", "label": "A", "path": "/a"}] * 2},
        {"pages": [{"slug": "a"}]},
    ],
)
def test_bad_config_is_refused(tmp_path, overrides):
    with pytest.raises(ConfigError):
        load_config(write_yaml(tmp_path, **overrides))


def test_missing_config_file_is_refused(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.yaml")


# --------------------------------------------------------------------------- network and runs


class Site:
    """A fictitious server: robots.txt plus the pages, with ETag support and a request log."""

    def __init__(self, pages: dict[str, str], robots: str = ROBOTS) -> None:
        self.pages = pages
        self.robots = robots
        self.calls: list[tuple[str, dict[str, str]]] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append((request.url.path, dict(request.headers)))
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text=self.robots)
        html = self.pages.get(request.url.path)
        if html is None:
            return httpx2.Response(404, text="introuvable")
        etag = f'"{hash(html) & 0xFFFFFF:x}"'
        if request.headers.get("If-None-Match") == etag:
            return httpx2.Response(304)
        return httpx2.Response(200, text=html, headers={"ETag": etag})

    def paths(self) -> list[str]:
        return [path for path, _ in self.calls]


def run(config, site, **kwargs):
    client = httpx2.Client(
        transport=httpx2.MockTransport(site.handler),
        headers={"User-Agent": config.user_agent},
        follow_redirects=True,
    )
    return run_extraction(config, client, now=lambda: NOW, sleep=lambda _: None, **kwargs)


def two_pages(second: str | None = None) -> dict[str, str]:
    return {
        PAGE.path: build_page(),
        "/fr-fr/release-health/status-fictive-b": second or build_page(),
    }


def test_full_run_writes_records_and_report(tmp_path):
    config = make_config(tmp_path)
    site = Site(two_pages())
    report = run(config, site)
    assert (report.issues_seen, report.new, report.updated, report.unchanged) == (6, 6, 0, 0)
    assert report.status == "ok" and report.requests == 3  # robots.txt + 2 pages
    assert report.by_status == {"resolved": 2, "mitigated": 2, "open": 2}
    assert report.fields_filled["title"] == 6
    assert report.fields_filled["originating_kb"] == 4  # « Non applicable » on 2 of 6
    assert report.fields_filled["resolving_kb"] == 2
    records = read_records(config.output_directory / "issues.jsonl")
    assert set(records) == {
        f"{slug}:{n}" for slug in ("fictive-a", "fictive-b") for n in (9001, 9002, 9003)
    }
    saved_report = json.loads((config.output_directory / "report.json").read_text(encoding="utf-8"))
    assert saved_report["issues_seen"] == 6 and saved_report["pages_downloaded"] == 2
    # Politeness: robots.txt first, identifying User-Agent on every request.
    assert site.paths()[0] == "/robots.txt"
    assert all(h["user-agent"] == config.user_agent for _, h in site.calls)


def test_second_run_uses_the_etag_and_downloads_nothing_new(tmp_path):
    config = make_config(tmp_path)
    site = Site(two_pages())
    run(config, site)
    report = run(config, site)
    assert report.pages_not_modified == 2 and report.pages_downloaded == 0
    assert (report.new, report.updated, report.unchanged, report.issues_seen) == (0, 0, 6, 6)
    page_calls = [h for p, h in site.calls if p != "/robots.txt"][2:]
    assert all("if-none-match" in h for h in page_calls)
    assert len((config.output_directory / "issues.jsonl").read_text("utf-8").splitlines()) == 6


def test_changed_issue_replaces_its_old_line(tmp_path):
    config = make_config(tmp_path)
    run(config, Site(two_pages()))
    changed = build_page().replace("Confirmé", "Résolu")
    report = run(config, Site(two_pages(second=changed)))
    assert report.updated == 1 and report.new == 0 and report.unchanged == 5
    lines = (config.output_directory / "issues.jsonl").read_text("utf-8").splitlines()
    assert len(lines) == 6  # compacted: one line per issue
    assert (
        read_records(config.output_directory / "issues.jsonl")["fictive-b:9003"]["status"]
        == "resolved"
    )


def test_etag_is_ignored_when_the_records_are_missing(tmp_path):
    config = make_config(tmp_path)
    site = Site(two_pages())
    run(config, site)
    (config.output_directory / "issues.jsonl").unlink()
    report = run(config, site)
    assert report.pages_downloaded == 2 and report.new == 6


def test_truncated_last_line_is_repaired_and_run_resumes(tmp_path):
    config = make_config(tmp_path)
    run(config, Site(two_pages()), only=["fictive-a"])
    path = config.output_directory / "issues.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"id": "fictive-b:90')  # interrupted run
    report = run(config, Site(two_pages()))
    assert report.new == 3 and report.unchanged == 3  # page B downloaded, page A not rewritten
    assert len(read_records(path)) == 6
    assert all(json.loads(line) for line in path.read_text("utf-8").splitlines())


def test_only_restricts_the_pages_and_rejects_unknown_slugs(tmp_path):
    config = make_config(tmp_path)
    site = Site(two_pages())
    report = run(config, site, only=["fictive-b"])
    assert report.pages_tracked == 1 and site.paths() == [
        "/robots.txt",
        "/fr-fr/release-health/status-fictive-b",
    ]
    with pytest.raises(ConfigError):
        run(config, site, only=["inconnue"])


def test_a_missing_page_is_reported_and_the_run_goes_on(tmp_path):
    config = make_config(tmp_path)
    report = run(config, Site({"/fr-fr/release-health/status-fictive-b": build_page()}))
    assert report.status == "partial" and report.new == 3
    assert report.failures[0]["page"] == "fictive-a" and "404" in report.failures[0]["error"]


def test_consecutive_failures_abort_the_run(tmp_path):
    pages = tuple(TrackedPage(f"p{i}", f"P{i}", f"/p{i}") for i in range(4))
    config = make_config(tmp_path, pages=pages, max_consecutive_failures=2)
    with pytest.raises(FetchError, match="échecs consécutifs"):
        run(config, Site({}))
    report = json.loads((config.output_directory / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "network_error"


def test_robots_forbidding_a_page_stops_the_run_without_visiting(tmp_path):
    config = make_config(tmp_path)
    site = Site(two_pages(), robots=f"User-agent: *\nDisallow: {PAGE.path}\n")
    with pytest.raises(RobotsError):
        run(config, site)
    assert site.paths() == ["/robots.txt"]
    report = json.loads((config.output_directory / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "robots_refused"


def test_unreadable_robots_stops_the_run(tmp_path):
    config = make_config(tmp_path)
    client = httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(403)))
    with pytest.raises(RobotsError):
        run_extraction(config, client, sleep=lambda _: None)


def test_missing_robots_means_no_restriction(tmp_path):
    config = make_config(tmp_path)
    fetcher = Fetcher(
        httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(404))),
        config,
        sleep=lambda _: None,
    )
    fetcher.load_robots()
    assert fetcher.robots.can_fetch(PAGE_URL)


def test_fetcher_requires_robots_to_be_read_first(tmp_path):
    fetcher = Fetcher(
        httpx2.Client(transport=httpx2.MockTransport(lambda r: httpx2.Response(200))),
        make_config(tmp_path),
    )
    with pytest.raises(RobotsError, match="n'a pas été lu"):
        fetcher.get_page(PAGE_URL)


def test_redirect_to_another_domain_is_refused(tmp_path):
    config = make_config(tmp_path, max_retries=0)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.host == BASE.removeprefix("https://"):
            if request.url.path == "/robots.txt":
                return httpx2.Response(200, text="")
            return httpx2.Response(302, headers={"Location": "https://ailleurs.test/page"})
        return httpx2.Response(200, text="autre domaine")

    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=True)
    fetcher = Fetcher(client, config, sleep=lambda _: None)
    fetcher.load_robots()
    with pytest.raises(FetchError, match="autre domaine"):
        fetcher.get_page(PAGE_URL)


def test_server_errors_are_retried_with_growing_delay(tmp_path):
    config = make_config(tmp_path, max_retries=2, backoff_seconds=3.0)
    attempts = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        attempts.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="")
        return httpx2.Response(503) if len(attempts) < 4 else httpx2.Response(200, text="<html/>")

    sleeps: list[float] = []
    fetcher = Fetcher(
        httpx2.Client(transport=httpx2.MockTransport(handler)), config, sleep=sleeps.append
    )
    fetcher.load_robots()
    assert fetcher.get_page(PAGE_URL).html == "<html/>"
    assert [s for s in sleeps if s >= 3.0] == [3.0, 6.0]


def test_network_errors_are_retried_then_reported(tmp_path):
    config = make_config(tmp_path, max_retries=1)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/robots.txt":
            return httpx2.Response(200, text="")
        raise httpx2.ConnectError("coupure")

    fetcher = Fetcher(
        httpx2.Client(transport=httpx2.MockTransport(handler)), config, sleep=lambda _: None
    )
    fetcher.load_robots()
    with pytest.raises(FetchError, match="échec après 2 essais"):
        fetcher.get_page(PAGE_URL)


def test_run_never_exceeds_one_request_per_two_seconds(tmp_path):
    config = make_config(tmp_path)
    clock = {"now": 0.0}
    stamps: list[float] = []
    site = Site(two_pages())

    def timed(request: httpx2.Request) -> httpx2.Response:
        stamps.append(clock["now"])
        return site.handler(request)

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    client = httpx2.Client(transport=httpx2.MockTransport(timed))
    run_extraction(config, client, now=lambda: NOW, sleep=sleep, clock=lambda: clock["now"])
    assert len(stamps) == 3
    assert all(b - a >= 2.0 for a, b in zip(stamps, stamps[1:], strict=False))


def test_page_structure_change_stops_the_run_with_a_dedicated_status(tmp_path):
    config = make_config(tmp_path)
    broken = Site({PAGE.path: "<html><body><p>Nouvelle mise en page</p></body></html>"})
    with pytest.raises(PageFormatError) as excinfo:
        run(config, broken)
    assert excinfo.value.exit_code == 4
    report = json.loads((config.output_directory / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "format_changed" and "h1" in report["error"]
    assert not (config.output_directory / "issues.jsonl").exists() or not read_records(
        config.output_directory / "issues.jsonl"
    )


def test_isolated_empty_page_is_accepted_and_reported(tmp_path):
    config = make_config(tmp_path)
    pages = {PAGE.path: build_page([]), "/fr-fr/release-health/status-fictive-b": build_page()}
    report = run(config, Site(pages))
    assert report.pages_empty == ["fictive-a"] and report.issues_seen == 3
    assert report.status == "ok"


def test_all_downloaded_pages_empty_is_a_structure_change(tmp_path):
    config = make_config(tmp_path)
    run(config, Site(two_pages()))  # existing output
    before = (config.output_directory / "issues.jsonl").read_text("utf-8")
    (config.output_directory / "state.json").unlink()  # force a full download
    empty = {PAGE.path: build_page([]), "/fr-fr/release-health/status-fictive-b": build_page([])}
    with pytest.raises(PageFormatError, match="changement de structure") as excinfo:
        run(config, Site(empty))
    assert excinfo.value.exit_code == 4
    assert (config.output_directory / "issues.jsonl").read_text("utf-8") == before
    report = json.loads((config.output_directory / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "format_changed" and report["pages_empty"] == [
        "fictive-a",
        "fictive-b",
    ]


def test_no_personal_or_ticket_content_in_the_logs(tmp_path, caplog):
    config = make_config(tmp_path)
    with caplog.at_level("INFO"):
        run(config, Site(two_pages()))
    assert "Problème fictif" not in caplog.text
    assert re.search(r"6 problèmes vus", caplog.text)

"""Tests of the CERT-FR extraction from its JSON API (Issue #42). No network call.

The JSON fixtures in tests/fixtures/certfr/ are reduced copies of real responses
(source: CERT-FR, https://cert.cyber.gouv.fr/, Licence Ouverte Etalab 2.0, see the README there).
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx2
import pytest

from src.data import certfr
from src.data.certfr import (
    ApiFormatError,
    CertfrConfig,
    ConfigError,
    Fetcher,
    FetchError,
    ListEntry,
    RateLimiter,
    RobotsError,
    api_date,
    load_config,
    normalize_system,
    parse_advisory,
    parse_list,
    parse_version,
    run_extraction,
)

FIXTURES = Path(__file__).parent / "fixtures" / "certfr"
BASE = "https://cert.cyber.gouv.fr"
LIST_URL = f"{BASE}/avis/json/"
ROBOTS = (
    "User-agent: *\nDisallow: /pdf\nDisallow: /tar\nDisallow: /js\n"
    "Disallow: /fonts\nDisallow: /fiche/\n"
)
TODAY = date(2026, 10, 23)


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_config(tmp_path: Path, **overrides) -> CertfrConfig:
    values = {
        "base_url": BASE,
        "user_agent": "test-agent/0.1 (https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES)",
        "min_interval_seconds": 2.0,
        "timeout_seconds": 5,
        "max_retries": 2,
        "backoff_seconds": 1.0,
        "max_consecutive_failures": 3,
        "months": 12,
        "output_directory": tmp_path / "out",
    }
    values.update(overrides)
    return CertfrConfig(**values)


def ref(n: int, year: int = 2026) -> str:
    return f"CERTFR-{year}-AVI-{n:04d}"


def list_item(reference: str, when: str | None, title: str = "Titre") -> dict:
    return {
        "json_url": f"/avis/{reference}/json/",
        "last_revision_date": f"{when}T00:00:00.000000" if when else None,
        "reference": reference,
        "scada": False,
        "title": f"{title} {reference}",
    }


def detail(reference: str) -> dict:
    data = copy.deepcopy(fixture("avis_1367.json"))
    data["reference"] = reference
    return data


class FakeSite:
    """Routes URLs to JSON (or a status code), records every request."""

    def __init__(self, pages: dict[str, object]):
        self.pages = pages
        self.requests: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        page = self.pages.get(str(request.url), 404)
        if isinstance(page, int):
            return httpx2.Response(page)
        if isinstance(page, str):
            return httpx2.Response(200, text=page)
        return httpx2.Response(200, json=page)

    def client(self) -> httpx2.Client:
        return httpx2.Client(transport=httpx2.MockTransport(self.handler))

    @property
    def urls(self) -> list[str]:
        return [str(r.url) for r in self.requests]


def detail_url(reference: str) -> str:
    return f"{BASE}/avis/{reference}/json/"


def standard_site(extra: dict | None = None, items: list[dict] | None = None) -> FakeSite:
    items = items or [
        list_item(ref(1), "2026-10-18"),
        list_item(ref(3), "2026-10-20"),
        list_item(ref(2), "2026-10-19"),
        list_item(ref(900, 2025), "2025-01-01"),  # older than 12 months
    ]
    pages: dict[str, object] = {f"{BASE}/robots.txt": ROBOTS, LIST_URL: items}
    for n in (1, 2, 3):
        pages[detail_url(ref(n))] = detail(ref(n))
    pages.update(extra or {})
    return FakeSite(pages)


def run(config, site, **kwargs):
    sleeps: list[float] = []
    kwargs.setdefault("today", TODAY)
    kwargs.setdefault("now", lambda: datetime(2026, 10, 23, 12, 0, tzinfo=UTC))
    report = run_extraction(config, site.client(), sleep=sleeps.append, **kwargs)
    return report, sleeps


def read_lines(tmp_path: Path) -> list[dict]:
    path = tmp_path / "out" / "avis.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def saved_report(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "out" / "report.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- parsing


def test_api_date_formats():
    assert api_date("2026-10-22T00:00:00.000000") == date(2026, 10, 22)
    assert api_date("2026-10-14") == date(2026, 10, 14)
    assert api_date(None) is None
    assert api_date("null") is None


@pytest.mark.parametrize("value", ["22 octobre 2026", "2026-13-40", 20261022])
def test_api_date_rejects_garbage(value):
    with pytest.raises(ApiFormatError):
        api_date(value)


def test_parse_list_fixture():
    entries = parse_list(fixture("list_sample.json"), BASE)
    assert [e.reference for e in entries] == [
        "CERTFR-2026-AVI-1367",
        "CERTFR-2026-AVI-1366",
        "CERTFR-2025-AVI-0251",
    ]
    assert entries[0].last_revision == date(2026, 10, 22)
    assert entries[0].url == f"{BASE}/avis/CERTFR-2026-AVI-1367/json/"
    assert entries[0].scada is False


@pytest.mark.parametrize(
    "payload",
    [
        {"erreur": "maintenance"},
        [],
        ["texte"],
        [{"reference": "XYZ", "title": "t", "json_url": "/avis/XYZ/json/"}],
        [{"reference": "CERTFR-2026-AVI-0001", "title": "t"}],
        [{"reference": "CERTFR-2026-AVI-0001", "title": "t", "json_url": "https://evil.example/x"}],
        [{"reference": "CERTFR-2026-AVI-0001", "title": "t", "json_url": "/fiche/x/"}],
    ],
)
def test_parse_list_rejects_unexpected_structure(payload):
    with pytest.raises(ApiFormatError):
        parse_list(payload, BASE)


def entry_for(reference: str, when: str | None = "2026-10-22") -> ListEntry:
    return ListEntry(
        reference, "t", date.fromisoformat(when) if when else None, False, detail_url(reference)
    )


def test_parse_advisory_complete():
    record = parse_advisory(
        fixture("avis_1367.json"), entry_for("CERTFR-2026-AVI-1367"), "2026-10-23T12:00:00+00:00"
    )
    assert record["reference"] == "CERTFR-2026-AVI-1367"
    assert record["title"] == "Multiples vulnérabilités dans Node"
    assert record["first_version_date"] == "2026-10-22"
    assert record["last_version_date"] == "2026-10-22"
    assert record["risks"] == [
        "Exécution de code arbitraire à distance",
        "Non spécifié par l'éditeur",
        "Contournement de la politique de sécurité",
    ]
    assert record["summary"].startswith("De multiples vulnérabilités ont été découvertes")
    assert record["cve"] == []
    assert record["vendor_advisories"] == [
        {
            "title": "Bulletin de sécurité Node.js october-2026-security-releases",
            "url": "https://nodejs.org/en/blog/vulnerability/october-2026-security-releases",
            "published_at": "2026-10-14",
        }
    ]
    assert record["revisions"] == [{"date": "2026-10-22", "description": "Version initiale"}]
    assert record["url"] == detail_url("CERTFR-2026-AVI-1367")
    assert record["extracted_at"] == "2026-10-23T12:00:00+00:00"
    assert record["scada"] is False
    node = record["affected_systems"][0]
    assert node == {
        "description": "Node.js versions 26.x antérieures à 26.12.1",
        "vendor": "Node.js",
        "product": "Node.js",
        "product_slug": "node-js",
        "branch": "26.x",
        "fixed_in": "26.12.1",
        "version_parsed": True,
    }


def test_parse_advisory_with_cves_and_several_products():
    record = parse_advisory(fixture("avis_1366.json"), entry_for("CERTFR-2026-AVI-1366"), "t")
    assert len(record["cve"]) == 3 and all(c.startswith("CVE-2026-") for c in record["cve"])
    assert len(record["vendor_advisories"]) == 2
    soar = next(s for s in record["affected_systems"] if "SOAR" in s["description"])
    assert (soar["vendor"], soar["product"], soar["branch"], soar["fixed_in"]) == (
        "Splunk",
        "SOAR",
        None,
        "8.7.0",
    )


def test_parse_advisory_old_one_strips_the_summary():
    record = parse_advisory(fixture("avis_0251.json"), entry_for("CERTFR-2025-AVI-0251"), "t")
    assert record["summary"].endswith("politique de sécurité.")
    assert record["cve"] == ["CVE-2025-2857"]
    assert {s["product"] for s in record["affected_systems"]} >= {"Firefox", "Firefox ESR"}


def test_parse_advisory_dates_fall_back_on_revisions_and_may_be_undefined():
    data = fixture("avis_1367.json")
    data["revisions"] = [
        {"description": "v2", "revision_date": "2026-10-25T00:00:00.000000"},
        {"description": "v1", "revision_date": "2026-10-22T00:00:00.000000"},
        {"description": "sans date"},
    ]
    record = parse_advisory(data, entry_for("CERTFR-2026-AVI-1367", None), "t")
    assert record["first_version_date"] == "2026-10-22"
    assert record["last_version_date"] == "2026-10-25"
    data["revisions"] = []
    record = parse_advisory(data, entry_for("CERTFR-2026-AVI-1367", None), "t")
    assert record["first_version_date"] is None and record["last_version_date"] is None


def test_parse_advisory_lists_may_be_empty_but_required_fields_are_checked():
    data = fixture("avis_1367.json")
    for key in ("affected_systems", "risks", "cves", "links", "vendor_advisories"):
        data[key] = []
    record = parse_advisory(data, entry_for("CERTFR-2026-AVI-1367"), "t")
    assert record["affected_systems"] == [] and record["risks"] == []

    def broken(**changes):
        copy_ = fixture("avis_1367.json")
        copy_.update(changes)
        return copy_

    entry = entry_for("CERTFR-2026-AVI-1367")
    with pytest.raises(ApiFormatError, match="résumé"):
        parse_advisory(broken(summary="  "), entry, "t")
    with pytest.raises(ApiFormatError, match="titre"):
        parse_advisory(broken(title=None), entry, "t")
    with pytest.raises(ApiFormatError, match="pas CERTFR-2026-AVI-1367"):
        parse_advisory(broken(reference="CERTFR-2026-AVI-0099"), entry, "t")
    with pytest.raises(ApiFormatError, match="« risks »"):
        parse_advisory(broken(risks="aucun"), entry, "t")
    with pytest.raises(ApiFormatError, match="« cves »"):
        parse_advisory(
            {k: v for k, v in fixture("avis_1367.json").items() if k != "cves"}, entry, "t"
        )
    with pytest.raises(ApiFormatError, match="sans texte"):
        parse_advisory(broken(risks=[{"description": None}]), entry, "t")
    with pytest.raises(ApiFormatError, match="description"):
        parse_advisory(broken(affected_systems=[{"product": {}}]), entry, "t")
    with pytest.raises(ApiFormatError, match="objet JSON"):
        parse_advisory(["x"], entry, "t")


@pytest.mark.parametrize(
    ("description", "branch", "fixed"),
    [
        ("Node.js versions 22.x antérieures à 22.23.4", "22.x", "22.23.4"),
        ("IOS XE Software versions 17.12.x et antérieures à 17.12.8", "17.12.x", "17.12.8"),
        ("Splunk SOAR versions antérieures à 8.7.0", None, "8.7.0"),
        ("Snort 3 versions 3.x antérieures à 3.12.4.0", "3.x", "3.12.4.0"),
        ("Bind versions antérieures à 9.20.30", None, "9.20.30"),
        (
            "Debian LTS 12 bookworm versions antérieures à 6.12.113-1~deb12u1",
            None,
            "6.12.113-1~deb12u1",
        ),
    ],
)
def test_parse_version_sure_cases(description, branch, fixed):
    assert parse_version(description) == (branch, fixed)


@pytest.mark.parametrize(
    "description",
    [
        "Expressway Series versions postérieures à X14 et antérieures à X15.5.20",
        "Secure Client versions postérieures à 5.1.20.333 et antérieures à 5.1.20.333",
        "IOS XR versions 24.1 et antérieures à 24.1.2 and SMU asr9k-x64-24.1.2.CSCwn39554",
        "Windows Server 2019",
        "",
    ],
)
def test_parse_version_unsure_cases_give_nothing(description):
    assert parse_version(description) == (None, None)


def test_normalize_system_uses_the_structured_names_and_handles_missing_ones():
    system = {
        "description": "Produit X   versions antérieures à 1.2",
        "product": {"name": "N/A", "vendor": {"name": "N/A", "scada": False}},
    }
    result = normalize_system(system)
    assert result["vendor"] is None and result["product"] is None
    assert result["product_slug"] is None
    assert result["description"] == "Produit X versions antérieures à 1.2"
    assert result["version_parsed"] is True
    # product or vendor object missing altogether
    assert normalize_system({"description": "Truc"})["product"] is None
    named = {"description": "IOS XE Software", "product": {"name": "IOS XE Software"}}
    assert normalize_system(named)["product_slug"] == "ios-xe-software"
    assert normalize_system(named)["version_parsed"] is False


# --------------------------------------------------------------------------- configuration


def test_real_config_loads_and_respects_the_floor():
    config = load_config()
    assert config.min_interval_seconds >= 2.0
    assert "github.com/timdazayous/Projet_Simplon_FIN_ETUDES" in config.user_agent


def test_config_refuses_a_faster_rate(tmp_path):
    text = certfr.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        text.replace("min_interval_seconds: 2.0", "min_interval_seconds: 0.5"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="minimum"):
        load_config(bad)


def test_config_refuses_missing_file_and_anonymous_user_agent(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.yaml")
    text = certfr.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    bad = tmp_path / "ua.yaml"
    lines = [
        ln if not ln.startswith("user_agent") else 'user_agent: "python"'
        for ln in text.splitlines()
    ]
    bad.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ConfigError, match="User-Agent"):
        load_config(bad)


# --------------------------------------------------------------------------- rate limit


def test_rate_limiter_sleeps_the_missing_time():
    now = [100.0]
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    limiter = RateLimiter(2.0, clock=lambda: now[0], sleep=sleep)
    limiter.wait()  # first request: no wait
    now[0] += 0.5
    limiter.wait()  # 0.5 s elapsed: wait 1.5 s
    now[0] += 5
    limiter.wait()  # already 5 s: no wait
    assert sleeps == [1.5]


def test_run_never_exceeds_one_request_per_two_seconds(tmp_path):
    site = standard_site()
    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    stamps: list[float] = []

    def timed(request):
        stamps.append(now[0])  # instant fake responses: only the limiter spaces the requests
        return site.handler(request)

    client = httpx2.Client(transport=httpx2.MockTransport(timed))
    run_extraction(
        make_config(tmp_path),
        client,
        today=TODAY,
        sleep=sleep,
        clock=lambda: now[0],
        now=lambda: datetime(2026, 10, 23, tzinfo=UTC),
    )
    assert len(stamps) == 5  # robots.txt, list, 3 advisories
    assert all(b - a >= 2.0 for a, b in zip(stamps, stamps[1:], strict=False))


# --------------------------------------------------------------------------- robots.txt


def test_robots_is_read_first_and_forbidden_path_is_never_requested(tmp_path):
    config = make_config(tmp_path)
    site = FakeSite({f"{BASE}/robots.txt": ROBOTS})
    fetcher = Fetcher(site.client(), config, sleep=lambda s: None)
    with pytest.raises(RobotsError, match="pas été lu"):
        fetcher.get_json(LIST_URL)
    fetcher.load_robots()
    assert site.urls == [f"{BASE}/robots.txt"]
    for forbidden in (f"{BASE}/fiche/CERTFR-X/", f"{BASE}/pdf/x.pdf", f"{BASE}/tar/x"):
        with pytest.raises(RobotsError, match="interdit"):
            fetcher.get_json(forbidden)
    assert site.urls == [f"{BASE}/robots.txt"]  # no request was sent for the forbidden paths


def test_robots_forbidding_avis_stops_the_run_without_visiting(tmp_path):
    site = FakeSite({f"{BASE}/robots.txt": "User-agent: *\nDisallow: /avis\n"})
    with pytest.raises(RobotsError):
        run(make_config(tmp_path), site)
    assert site.urls == [f"{BASE}/robots.txt"]
    assert saved_report(tmp_path)["status"] == "robots_refused"


def test_unreadable_robots_aborts_by_caution(tmp_path):
    site = FakeSite({f"{BASE}/robots.txt": 403})
    with pytest.raises(RobotsError):
        run(make_config(tmp_path), site)
    assert site.urls == [f"{BASE}/robots.txt"]


def test_missing_robots_means_no_restriction(tmp_path):
    config = make_config(tmp_path)
    site = FakeSite({})  # 404 on robots.txt
    fetcher = Fetcher(site.client(), config, sleep=lambda s: None)
    fetcher.load_robots()
    assert fetcher.robots.can_fetch("x", LIST_URL)


# --------------------------------------------------------------------------- retries


def ready_fetcher(tmp_path, handler, **overrides) -> tuple[Fetcher, list[float]]:
    sleeps: list[float] = []
    client = httpx2.Client(transport=httpx2.MockTransport(handler), follow_redirects=True)
    fetcher = Fetcher(client, make_config(tmp_path, **overrides), sleep=sleeps.append)
    fetcher.robots = certfr.RobotFileParser()
    fetcher.robots.parse([])
    return fetcher, sleeps


def test_retries_with_growing_delay_then_succeeds(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx2.Response(503)
        return httpx2.Response(200, json={"ok": True})

    fetcher, sleeps = ready_fetcher(tmp_path, handler)
    assert fetcher.get_json(LIST_URL) == {"ok": True}
    assert calls["n"] == 3
    assert 1.0 in sleeps and 2.0 in sleeps  # backoff 1 s then 2 s


def test_timeout_is_retried_then_reported(tmp_path):
    def handler(request):
        raise httpx2.ReadTimeout("slow", request=request)

    fetcher, _ = ready_fetcher(tmp_path, handler, max_retries=1)
    with pytest.raises(FetchError, match="2 essais"):
        fetcher.get_json(LIST_URL)
    assert fetcher.requests_made == 2


def test_redirect_to_another_domain_is_refused(tmp_path):
    def handler(request):
        if request.url.host == "cert.cyber.gouv.fr":
            return httpx2.Response(302, headers={"location": "https://evil.example/x"})
        return httpx2.Response(200, json=[])

    fetcher, _ = ready_fetcher(tmp_path, handler)
    with pytest.raises(FetchError, match="autre domaine"):
        fetcher.get_json(LIST_URL)


def test_non_json_answer_is_a_format_error(tmp_path):
    fetcher, _ = ready_fetcher(tmp_path, lambda r: httpx2.Response(200, text="<html>Maintenance"))
    with pytest.raises(ApiFormatError, match="JSON"):
        fetcher.get_json(LIST_URL)


def test_requests_ask_for_json(tmp_path):
    seen = []

    def handler(request):
        seen.append(request.headers["accept"])
        return httpx2.Response(200, json=[])

    fetcher, _ = ready_fetcher(tmp_path, handler)
    fetcher.get_json(LIST_URL)
    assert seen == ["application/json"]


# --------------------------------------------------------------------------- full runs


def test_full_run_filters_the_period_and_writes_report(tmp_path):
    report, _ = run(make_config(tmp_path), standard_site())
    assert sorted(r["reference"] for r in read_lines(tmp_path)) == [ref(1), ref(2), ref(3)]
    assert report.list_entries == 4 and report.in_period == 3 and report.outside_period == 1
    assert report.avis_written == 3 and report.revised == 0 and report.status == "ok"
    saved = saved_report(tmp_path)
    assert saved["requests"] == report.requests == 5  # robots.txt, list, 3 advisories
    assert saved["systems_total"] == 9 and saved["systems_version_parsed"] == 9
    assert saved["systems_with_vendor_and_product"] == 9


def test_user_agent_identifies_the_project_on_every_request(tmp_path):
    config = make_config(tmp_path)
    site = standard_site()
    with httpx2.Client(
        transport=httpx2.MockTransport(site.handler), headers={"User-Agent": config.user_agent}
    ) as client:
        run_extraction(
            config,
            client,
            today=TODAY,
            sleep=lambda s: None,
            now=lambda: datetime(2026, 10, 23, tzinfo=UTC),
        )
    assert {r.headers["user-agent"] for r in site.requests} == {config.user_agent}
    assert "github.com/timdazayous" in config.user_agent


def test_limit_keeps_the_newest_advisories(tmp_path):
    site = standard_site()
    report, _ = run(make_config(tmp_path), site, limit=2)
    assert report.avis_written == 2
    assert [r["reference"] for r in read_lines(tmp_path)] == [ref(3), ref(2)]
    assert detail_url(ref(1)) not in site.urls


def test_incremental_run_downloads_only_new_advisories(tmp_path):
    config = make_config(tmp_path)
    run(config, standard_site())
    second = standard_site()
    report, _ = run(config, second)
    assert report.avis_written == 0 and report.up_to_date == 3
    assert second.urls == [f"{BASE}/robots.txt", LIST_URL]  # no advisory re-downloaded
    assert len(read_lines(tmp_path)) == 3
    items = [list_item(ref(4), "2026-10-22"), list_item(ref(3), "2026-10-20")]
    third = standard_site({detail_url(ref(4)): detail(ref(4))}, items)
    report, _ = run(config, third)
    assert report.avis_written == 1 and detail_url(ref(3)) not in third.urls
    assert sorted(r["reference"] for r in read_lines(tmp_path)) == [ref(1), ref(2), ref(3), ref(4)]


def test_revised_advisory_is_downloaded_again_and_replaces_the_old_line(tmp_path):
    config = make_config(tmp_path)
    run(config, standard_site())
    revised = detail(ref(2))
    revised["summary"] = "Résumé mis à jour."
    items = [
        list_item(ref(3), "2026-10-20"),
        list_item(ref(2), "2026-10-22"),  # revised on 22 October (was 19 October)
        list_item(ref(1), "2026-10-18"),
    ]
    site = standard_site({detail_url(ref(2)): revised}, items)
    report, _ = run(config, site)
    assert report.revised == 1 and report.avis_written == 1 and report.up_to_date == 2
    assert site.urls.count(detail_url(ref(2))) == 1
    records = {r["reference"]: r for r in read_lines(tmp_path)}
    assert len(read_lines(tmp_path)) == 3  # compacted: one line per advisory
    assert records[ref(2)]["summary"] == "Résumé mis à jour."
    assert records[ref(2)]["last_version_date"] == "2026-10-22"


def test_truncated_last_line_is_repaired(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    saved = {"reference": ref(3), "last_version_date": "2026-10-20"}
    (out / "avis.jsonl").write_text(json.dumps(saved) + '\n{"refer', encoding="utf-8")
    report, _ = run(make_config(tmp_path), standard_site())
    assert report.up_to_date == 1 and report.avis_written == 2
    lines = (out / "avis.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["reference"] for line in lines] == [ref(3), ref(2), ref(1)]


def test_advisories_without_a_date_are_counted_not_silently_dropped(tmp_path):
    items = [list_item(ref(1), None), list_item(ref(2), "2026-10-19")]
    report, _ = run(make_config(tmp_path), standard_site(items=items))
    assert report.without_date == 1 and report.avis_written == 1


def test_api_format_change_stops_the_run_with_the_report(tmp_path):
    site = standard_site({detail_url(ref(2)): {"erreur": "nouveau format"}})
    with pytest.raises(ApiFormatError):
        run(make_config(tmp_path), site)
    assert [r["reference"] for r in read_lines(tmp_path)] == [ref(3)]
    report = saved_report(tmp_path)
    assert report["status"] == "format_changed"
    assert "CERTFR-2026-AVI-0002" in report["error"]


def test_bad_list_stops_the_run(tmp_path):
    with pytest.raises(ApiFormatError, match="Liste"):
        run(make_config(tmp_path), standard_site(items=[{"reference": "X"}]))
    assert saved_report(tmp_path)["status"] == "format_changed"


def test_one_failed_advisory_is_reported_and_the_run_goes_on(tmp_path):
    site = standard_site({detail_url(ref(2)): 404})
    report, _ = run(make_config(tmp_path), site)
    assert report.status == "partial"
    assert [f["reference"] for f in report.failures] == [ref(2)]
    assert report.avis_written == 2


def test_consecutive_failures_abort_the_run(tmp_path):
    site = standard_site({detail_url(ref(n)): 404 for n in (1, 2, 3)})
    with pytest.raises(FetchError, match="consécutifs"):
        run(make_config(tmp_path, max_consecutive_failures=2), site)
    assert saved_report(tmp_path)["status"] == "network_error"


def test_exit_codes_are_distinct():
    codes = [
        certfr.EXIT_OK,
        certfr.EXIT_PARTIAL,
        ConfigError.exit_code,
        RobotsError.exit_code,
        ApiFormatError.exit_code,
        FetchError.exit_code,
    ]
    assert len(set(codes)) == len(codes)

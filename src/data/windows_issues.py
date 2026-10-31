"""Scrape the known issues of the Windows updates (Issue #45, source 5: scraping).

Source: the public French pages "Windows release health" of Microsoft Learn
(``https://learn.microsoft.com/fr-fr/windows/release-health/``), one page per tracked Windows
version. Microsoft publishes no free structured access to this information (no RSS or JSON feed;
the Microsoft Graph ``windowsUpdates`` API needs a licensed tenant and an administrator role), see
``docs/donnees/windows-known-issues.md``. The pages are static HTML (no JavaScript is needed), so
``httpx2`` downloads and BeautifulSoup parses.

Steps of :func:`run_extraction`: initialise (read the configuration, read and obey
``robots.txt``, read the records already saved), download each tracked page (conditional request
with the saved ``ETag``), parse it, append the new or changed issues to
``data/raw/windows_known_issues/issues.jsonl`` (ignored by Git), compact the file and write an
execution report.

Terms of use of Microsoft Learn: personal and non-commercial use only; no copy, publication or
redistribution. Therefore nothing extracted here is versioned: the data stays in ``data/raw/``
(ignored by Git), and the tests use fictitious HTML that only reproduces the tag structure.

Respect of the source (not negotiable): ``robots.txt`` is read at start and every URL is checked
against it, the User-Agent names the project and its repository, at most one request every
``min_interval_seconds`` (never below 2 s), redirections to another domain are refused.

A page that does not have the expected structure raises :class:`PageFormatError` (dedicated exit
code) instead of producing records with empty fields.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2
import yaml
from bs4 import BeautifulSoup, Tag

from src.data.certfr import (
    EXIT_CONFIG,
    EXIT_FORMAT,
    EXIT_NETWORK,
    EXIT_OK,
    EXIT_PARTIAL,
    EXIT_ROBOTS,
    MIN_ALLOWED_INTERVAL,
    ConfigError,
    ExtractionError,
    FetchError,
    RateLimiter,
    RobotsError,
)

__all__ = [
    "EXIT_CONFIG",
    "EXIT_FORMAT",
    "EXIT_NETWORK",
    "EXIT_OK",
    "EXIT_PARTIAL",
    "EXIT_ROBOTS",
]

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "windows_issues.yaml"

# Fields whose fill rate is reported (a field that is "not applicable" on the page stays empty).
RECORD_FIELDS = (
    "title",
    "summary",
    "status",
    "originating_build",
    "originating_kb",
    "originating_date",
    "resolving_kb",
    "published_at",
    "last_updated_at",
    "platforms",
)


class PageFormatError(ExtractionError):
    """The page does not have the expected structure (Microsoft probably changed the layout)."""

    exit_code = EXIT_FORMAT
    status = "format_changed"


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class TrackedPage:
    slug: str
    label: str
    path: str


@dataclass(frozen=True)
class WindowsIssuesConfig:
    base_url: str
    user_agent: str
    min_interval_seconds: float
    timeout_seconds: float
    max_retries: int
    backoff_seconds: float
    max_consecutive_failures: int
    output_directory: Path
    pages: tuple[TrackedPage, ...]

    def page_url(self, page: TrackedPage) -> str:
        return f"{self.base_url}{page.path}"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> WindowsIssuesConfig:
    """Read ``config/windows_issues.yaml``; refuse a rate faster than one request per 2 s."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        pages = tuple(
            TrackedPage(slug=str(p["slug"]), label=str(p["label"]), path=str(p["path"]))
            for p in raw["pages"]
        )
        config = WindowsIssuesConfig(
            base_url=str(raw["base_url"]).rstrip("/"),
            user_agent=str(raw["user_agent"]),
            min_interval_seconds=float(raw["min_interval_seconds"]),
            timeout_seconds=float(raw["timeout_seconds"]),
            max_retries=int(raw["max_retries"]),
            backoff_seconds=float(raw["backoff_seconds"]),
            max_consecutive_failures=int(raw["max_consecutive_failures"]),
            output_directory=Path(raw["output_directory"]),
            pages=pages,
        )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        raise ConfigError(f"Configuration illisible ou incomplète ({path}) : {error!r}") from error
    if not config.pages:
        raise ConfigError("Aucune page suivie dans la configuration.")
    if len({p.slug for p in config.pages}) != len(config.pages):
        raise ConfigError("Deux pages suivies ont le même identifiant (slug).")
    if config.min_interval_seconds < MIN_ALLOWED_INTERVAL:
        raise ConfigError(
            f"min_interval_seconds={config.min_interval_seconds} : le minimum accepté est "
            f"{MIN_ALLOWED_INTERVAL} s (une requête toutes les 2 secondes au plus)."
        )
    if "github.com" not in config.user_agent:
        raise ConfigError("Le User-Agent doit identifier le projet et son dépôt GitHub.")
    return config


# --------------------------------------------------------------------------- normalisation


def _ascii_lower(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _clean(text: str) -> str:
    """Collapse every run of whitespace (non-breaking spaces included) into one space."""
    return " ".join(text.replace("\xa0", " ").split())


_OPEN_WORDS = ("confirm", "enquet", "examen", "investig", "signal", "ouvert", "rapport")


def normalize_status(raw: str) -> tuple[str, bool]:
    """French status of the page to ``(open | mitigated | resolved, external)``.

    ``external`` is true for « Atténué : externe » and « Résolu : externe » (third-party cause).
    An unknown wording raises :class:`PageFormatError`: guessing would hide a change of the page.
    """
    text = _ascii_lower(_clean(raw))
    external = "externe" in text
    if text.startswith("resolu"):
        return "resolved", external
    if text.startswith("attenue"):
        return "mitigated", external
    if any(word in text for word in _OPEN_WORDS):
        return "open", external
    raise PageFormatError(f"Statut inconnu : {raw!r} (ni résolu, ni atténué, ni ouvert).")


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def pacific_to_utc(local: datetime) -> datetime:
    """Convert a naive Pacific Time (« PT » on the pages) to an aware UTC datetime.

    United States rule: daylight saving time (UTC-7) from the second Sunday of March at 02:00 to
    the first Sunday of November at 02:00, otherwise UTC-8. Written by hand to avoid a ``tzdata``
    dependency (the standard ``zoneinfo`` has no timezone database on Windows).
    """
    start = datetime.combine(_nth_weekday(local.year, 3, 6, 2), datetime.min.time()) + timedelta(
        hours=2
    )
    end = datetime.combine(_nth_weekday(local.year, 11, 6, 1), datetime.min.time()) + timedelta(
        hours=2
    )
    offset = 7 if start <= local < end else 8
    return (local + timedelta(hours=offset)).replace(tzinfo=UTC)


_DATE_TIME_PT = re.compile(r"(\d{4}-\d{2}-\d{2})[ ,]*(\d{1,2})[:h](\d{2})\s*PT")
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_pt_datetime(text: str) -> str:
    """``"2026-10-13 10:13 PT"`` or ``"2026-10-08 17h44 PT"`` to an ISO 8601 UTC string."""
    match = _DATE_TIME_PT.search(_clean(text))
    if not match:
        raise PageFormatError(f"Date et heure au format inattendu : {text!r}")
    day, hour, minute = match.groups()
    try:
        local = datetime.fromisoformat(day).replace(hour=int(hour), minute=int(minute))
    except ValueError as error:
        raise PageFormatError(f"Date et heure invalides : {text!r}") from error
    return pacific_to_utc(local).isoformat().replace("+00:00", "Z")


def parse_iso_date(text: str) -> str:
    match = _DATE_ONLY.search(text)
    if not match:
        raise PageFormatError(f"Date au format inattendu : {text!r}")
    try:
        return date.fromisoformat(match.group()).isoformat()
    except ValueError as error:
        raise PageFormatError(f"Date invalide : {text!r}") from error


# --------------------------------------------------------------------------- parsing

_KB = re.compile(r"KB\s?(\d{6,8})", re.IGNORECASE)
_BUILD = re.compile(r"\b(\d{4,5}\.\d{1,5})\b")
_ANCHOR = re.compile(r"^#(\d+)msgdesc$")
EXPECTED_HEADERS = ("resume", "mise a jour d'origine", "statut", "derniere mise a jour")


def _cell_text(cell: Tag) -> str:
    return _clean(cell.get_text(" "))


def _find_summary_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table"):
        headers = tuple(_ascii_lower(_clean(th.get_text(" "))) for th in table.find_all("th"))
        if headers[:4] == EXPECTED_HEADERS:
            return table
    return None


def _first_line(cell: Tag) -> str:
    for text in cell.stripped_strings:
        return _clean(text)
    return ""


def parse_summary_row(row: Tag) -> dict[str, Any]:
    """One row of the « Problèmes connus » table (summary, origin, status, last update)."""
    cells = row.find_all("td")
    if len(cells) != 4:
        raise PageFormatError(
            f"Ligne du tableau récapitulatif à {len(cells)} colonnes, 4 attendues."
        )
    summary_cell, origin_cell, status_cell, updated_cell = cells

    link = summary_cell.find("a", href=_ANCHOR)
    if link is None:
        raise PageFormatError("Ligne sans lien vers le détail du problème (#NNNNmsgdesc).")
    issue_id = _ANCHOR.match(link["href"]).group(1)  # type: ignore[union-attr]
    title = _clean(link.get_text(" "))
    summary = _clean(
        " ".join(
            node.get_text(" ") if isinstance(node, Tag) else str(node)
            for node in summary_cell.children
            if node is not link and not (isinstance(node, Tag) and node.name in ("div", "br"))
        )
    )
    if not title:
        raise PageFormatError(f"Problème {issue_id} : titre vide.")

    origin_text = _cell_text(origin_cell)
    kb = _KB.search(origin_text)
    build = _BUILD.search(origin_text)
    origin_date = _DATE_ONLY.search(origin_text)
    if (
        not (kb or build or origin_date)
        and "non applicable" not in _ascii_lower(origin_text)
        and origin_text
    ):
        raise PageFormatError(f"Problème {issue_id} : mise à jour d'origine illisible.")

    status_raw = _first_line(status_cell)
    status, external = normalize_status(status_raw)
    resolving = _KB.search(_cell_text(status_cell))
    return {
        "issue_id": issue_id,
        "title": title,
        "summary": summary or None,
        "status_raw": status_raw,
        "status": status,
        "status_external": external,
        "originating_build": build.group(1) if build else None,
        "originating_kb": f"KB{kb.group(1)}" if kb else None,
        "originating_date": origin_date.group() if origin_date else None,
        "resolving_kb": f"KB{resolving.group(1)}" if resolving else None,
        "last_updated_at": parse_pt_datetime(_cell_text(updated_cell)),
    }


def _is_block_end(tag: Tag) -> bool:
    if tag.name in ("h2", "h3"):
        return True
    return tag.name == "div" and bool(re.search(r"msgdesc$", tag.get("id") or ""))


def _parse_history(table: Tag | None, issue_id: str) -> list[dict[str, str]]:
    """The « Historique » cell: lines like « Résolu : 2026-10-13, 10:00 PT »."""
    if table is None:
        return []
    rows = table.find_all("tr")
    if len(rows) < 2:
        raise PageFormatError(f"Problème {issue_id} : tableau de détail sans ligne de données.")
    cells = rows[1].find_all("td")
    if len(cells) < 3:
        raise PageFormatError(f"Problème {issue_id} : tableau de détail à {len(cells)} colonnes.")
    history = []
    for line in cells[2].stripped_strings:
        text = _clean(line)
        label, _, moment = text.partition(" : ")
        if not moment:
            raise PageFormatError(f"Problème {issue_id} : ligne d'historique illisible.")
        history.append({"status_raw": label, "at": parse_pt_datetime(moment)})
    return history


def _split_list(text: str) -> list[str]:
    text = _clean(text)
    if not text or _ascii_lower(text) in ("aucun", "aucune"):
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _parse_platforms(block: list[Tag]) -> dict[str, list[str]] | None:
    """The list that follows « Plateformes affectées : » (Client / Serveur), ``None`` if absent."""
    # The paragraph is sometimes nested in an indented ``div`` (editor artefact): search them all.
    paragraphs = [p for tag in block for p in ([tag] if tag.name == "p" else tag.find_all("p"))]
    for paragraph in paragraphs:
        if "plateformes affectees" in _ascii_lower(_cell_text(paragraph)):
            following = paragraph.find_next_sibling()
            if following is None or following.name != "ul":
                return None
            platforms: dict[str, list[str]] = {"client": [], "server": []}
            for item in following.find_all("li"):
                label, _, values = _clean(item.get_text(" ")).partition(" : ")
                if not values:
                    label, _, values = _clean(item.get_text(" ")).partition(":")
                key = {"client": "client", "serveur": "server"}.get(_ascii_lower(label).strip())
                if key:
                    platforms[key] = _split_list(values)
            return platforms
    return None


def parse_detail(soup: BeautifulSoup, issue_id: str) -> dict[str, Any]:
    """The detail block of one issue: history (opening date) and affected platforms."""
    anchor = soup.find("div", id=f"{issue_id}msgdesc")
    if anchor is None:
        raise PageFormatError(f"Problème {issue_id} : bloc de détail (#{issue_id}msgdesc) absent.")
    block: list[Tag] = []
    for sibling in anchor.find_next_siblings():
        if _is_block_end(sibling):
            break
        block.append(sibling)
    history = _parse_history(next((t for t in block if t.name == "table"), None), issue_id)
    published = min((h["at"] for h in history), default=None)
    return {
        "published_at": published,
        "history": history,
        "platforms": _parse_platforms(block),
    }


def parse_page(
    html: str, page: TrackedPage, page_url: str, extracted_at: str
) -> list[dict[str, Any]]:
    """All known issues of one page, as flat records.

    Raises :class:`PageFormatError` when the structure is not the expected one. A page whose
    « Problèmes connus » section holds no table and no detail block has no known issue: it returns
    an empty list (the run reports it so that it can be checked).
    """
    soup = BeautifulSoup(html, "html.parser")
    if soup.find("h1") is None:
        raise PageFormatError(f"{page.slug} : titre de page (h1) introuvable.")
    section = next(
        (
            h
            for h in soup.find_all("h2")
            if "problemes connus" in _ascii_lower(_clean(h.get_text()))
        ),
        None,
    )
    if section is None:
        raise PageFormatError(f"{page.slug} : section « Problèmes connus » introuvable.")
    table = _find_summary_table(soup)
    details = soup.find_all("div", id=re.compile(r"^\d+msgdesc$"))
    if table is None:
        if details:
            raise PageFormatError(
                f"{page.slug} : détails présents mais tableau récapitulatif absent."
            )
        return []
    body = table.find("tbody")
    rows = body.find_all("tr") if body else []
    if not rows:
        raise PageFormatError(f"{page.slug} : tableau récapitulatif sans ligne.")

    records = []
    seen: set[str] = set()
    for row in rows:
        summary = parse_summary_row(row)
        issue_id = summary["issue_id"]
        if issue_id in seen:
            raise PageFormatError(f"{page.slug} : problème {issue_id} en double.")
        seen.add(issue_id)
        detail = parse_detail(soup, issue_id)
        records.append(
            {
                "id": f"{page.slug}:{issue_id}",
                "windows_version": page.label,
                "page_slug": page.slug,
                **summary,
                **detail,
                "url": f"{page_url}#{issue_id}msgdesc",
                "page_url": page_url,
                "extracted_at": extracted_at,
            }
        )
    orphans = {d["id"].removesuffix("msgdesc") for d in details} - seen
    if orphans:
        raise PageFormatError(
            f"{page.slug} : détails sans ligne récapitulative ({sorted(orphans)})."
        )
    return records


# --------------------------------------------------------------------------- robots.txt


class RobotsRules:
    """Minimal robots.txt reader that understands ``*`` and ``$`` (the standard library's
    ``RobotFileParser`` does not, and learn.microsoft.com uses patterns such as ``/*/search/``)."""

    def __init__(self, text: str, user_agent: str) -> None:
        token = _ascii_lower(user_agent).split("/")[0].strip()
        groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[bool, str]] = []
        collecting_agents = False
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                if not collecting_agents:
                    agents, rules = [], []
                    groups.append((agents, rules))
                agents.append(value.lower())
                collecting_agents = True
            elif key in ("allow", "disallow"):
                collecting_agents = False
                if value:  # an empty Disallow means « everything is allowed »
                    rules.append((key == "allow", value))
        specific = [r for a, r in groups if any(x != "*" and x in token for x in a)]
        generic = [r for a, r in groups if "*" in a]
        self._rules = [rule for group in (specific or generic) for rule in group]

    @staticmethod
    def _matches(pattern: str, target: str) -> bool:
        regex = re.escape(pattern).replace(r"\*", ".*")
        if regex.endswith(r"\$"):
            regex = regex[: -len(r"\$")] + "$"
        return re.match(regex, target) is not None

    def can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        matching = [(len(p), allow) for allow, p in self._rules if self._matches(p, target)]
        if not matching:
            return True
        # Longest pattern wins; on a tie, Allow wins (Google's rule, followed by most crawlers).
        return max(matching, key=lambda m: (m[0], m[1]))[1]


# --------------------------------------------------------------------------- network


@dataclass
class PageResponse:
    html: str | None  # None when the page is unchanged since the saved ETag (HTTP 304)
    etag: str | None


class Fetcher:
    """Polite HTTP access: robots.txt check, rate limit, timeout, retries with growing delay."""

    def __init__(
        self,
        client: httpx2.Client,
        config: WindowsIssuesConfig,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.config = config
        self._sleep = sleep
        self.limiter = RateLimiter(config.min_interval_seconds, clock=clock, sleep=sleep)
        self.robots: RobotsRules | None = None
        self.requests_made = 0

    def load_robots(self) -> None:
        """Read robots.txt (404 means no restriction; any other failure refuses to go on)."""
        try:
            response = self._request(f"{self.config.base_url}/robots.txt", {})
        except FetchError as error:
            raise RobotsError(f"robots.txt illisible, abandon par prudence : {error}") from error
        if response.status_code == 404:
            self.robots = RobotsRules("", self.config.user_agent)
        elif response.status_code == 200:
            self.robots = RobotsRules(response.text, self.config.user_agent)
        else:
            raise RobotsError(f"robots.txt : réponse HTTP {response.status_code}, abandon.")

    def get_page(self, url: str, etag: str | None = None) -> PageResponse:
        """Download one HTML page after checking robots.txt. HTTP 404 raises :class:`FetchError`."""
        if self.robots is None:
            raise RobotsError("robots.txt n'a pas été lu : appeler load_robots() d'abord.")
        if not self.robots.can_fetch(url):
            raise RobotsError(f"robots.txt interdit {url} : aucune requête envoyée.")
        headers = {"If-None-Match": etag} if etag else {}
        response = self._request(url, headers)
        if response.status_code == 304:
            return PageResponse(html=None, etag=etag)
        if response.status_code != 200:
            raise FetchError(f"{url} : HTTP {response.status_code}")
        return PageResponse(html=response.text, etag=response.headers.get("ETag"))

    def _request(self, url: str, headers: dict[str, str]) -> httpx2.Response:
        base_host = urlparse(self.config.base_url).hostname
        last_error = "inconnue"
        headers = {"Accept": "text/html,text/plain;q=0.9", "Accept-Language": "fr-FR", **headers}
        for attempt in range(self.config.max_retries + 1):
            if attempt:
                self._sleep(self.config.backoff_seconds * 2 ** (attempt - 1))
            self.limiter.wait()
            self.requests_made += 1
            try:
                response = self.client.get(url, headers=headers)
            except httpx2.TransportError as error:  # includes timeouts and connection errors
                last_error = type(error).__name__
                logger.warning("Erreur réseau (%s), tentative %d", last_error, attempt + 1)
                continue
            if urlparse(str(response.url)).hostname != base_host:
                raise FetchError(f"{url} : redirection vers un autre domaine, refusée.")
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
                logger.warning("%s, tentative %d", last_error, attempt + 1)
                continue
            return response
        raise FetchError(f"{url} : échec après {self.config.max_retries + 1} essais ({last_error})")


# --------------------------------------------------------------------------- storage


def read_records(path: Path) -> dict[str, dict[str, Any]]:
    """Records of ``issues.jsonl`` by id; the last line of an id wins and a truncated line
    (interrupted run) is ignored."""
    records: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                records[record["id"]] = record
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return records


def compact(path: Path) -> None:
    """Rewrite the file with one line per id (a changed issue replaces its old line)."""
    if not path.exists():
        return
    records = read_records(path)
    temporary = path.with_suffix(".jsonl.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records.values():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def _append_line(path: Path, record: dict[str, Any]) -> None:
    needs_newline = path.exists() and path.stat().st_size > 0
    if needs_newline:
        with path.open("rb") as handle:
            handle.seek(-1, 2)
            needs_newline = handle.read(1) != b"\n"
    with path.open("a", encoding="utf-8") as handle:
        if needs_newline:  # a previous run was interrupted in the middle of a line
            handle.write("\n")
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_state(path: Path) -> dict[str, str]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in state.items()}
    except (OSError, ValueError, AttributeError):
        return {}


def _write_state(path: Path, state: dict[str, str]) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _comparable(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != "extracted_at"}


# --------------------------------------------------------------------------- run


@dataclass
class ExtractionReport:
    source: str = "windows_known_issues"
    status: str = "ok"
    error: str | None = None
    started_at: str = ""
    duration_seconds: float = 0.0
    requests: int = 0
    pages_tracked: int = 0
    pages_downloaded: int = 0
    pages_not_modified: int = 0
    pages_empty: list[str] = field(default_factory=list)
    issues_seen: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    fields_filled: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, str]] = field(default_factory=list)


def run_extraction(
    config: WindowsIssuesConfig,
    client: httpx2.Client,
    *,
    only: list[str] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> ExtractionReport:
    """Run the whole extraction. The report is written even when the run stops on an error."""
    started = clock()
    report = ExtractionReport(started_at=now().isoformat(timespec="seconds"))
    output_dir = config.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "issues.jsonl"
    fetcher = Fetcher(client, config, sleep=sleep, clock=clock)
    try:
        compact(output_path)  # drop a truncated line left by an interrupted run
        _extract(config, fetcher, report, output_dir, only, now)
    except ExtractionError as error:
        report.status, report.error = error.status, str(error)
        raise
    finally:
        compact(output_path)
        report.requests = fetcher.requests_made
        report.duration_seconds = round(clock() - started, 1)
        if report.status == "ok" and report.failures:
            report.status = "partial"
        (output_dir / "report.json").write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        logger.info(
            "windows_known_issues : %d problèmes vus (%d nouveaux, %d modifiés), %d requêtes, "
            "%.1f s, statut %s",
            report.issues_seen,
            report.new,
            report.updated,
            report.requests,
            report.duration_seconds,
            report.status,
        )
    return report


def _extract(
    config: WindowsIssuesConfig,
    fetcher: Fetcher,
    report: ExtractionReport,
    output_dir: Path,
    only: list[str] | None,
    now: Callable[[], datetime],
) -> None:
    output_path = output_dir / "issues.jsonl"
    state_path = output_dir / "state.json"
    pages = [p for p in config.pages if only is None or p.slug in only]
    unknown = set(only or []) - {p.slug for p in config.pages}
    if unknown:
        raise ConfigError(f"Page(s) non suivie(s) : {sorted(unknown)}")
    report.pages_tracked = len(pages)

    fetcher.load_robots()  # initialisation: nothing is visited before this succeeds
    saved = read_records(output_path)
    state = _read_state(state_path)
    statuses: Counter[str] = Counter()
    filled: Counter[str] = Counter()

    def count(record: dict[str, Any]) -> None:
        report.issues_seen += 1
        statuses[record["status"]] += 1
        for name in RECORD_FIELDS:
            filled[name] += record.get(name) not in (None, "", [])

    consecutive_failures = 0
    try:
        for page in pages:
            url = config.page_url(page)
            has_records = any(r["page_slug"] == page.slug for r in saved.values())
            try:
                # A saved ETag is only trusted if the records of the page are still on disk.
                response = fetcher.get_page(url, state.get(page.slug) if has_records else None)
            except FetchError as error:
                report.failures.append({"page": page.slug, "error": str(error)})
                consecutive_failures += 1
                if consecutive_failures >= config.max_consecutive_failures:
                    raise FetchError(
                        f"{consecutive_failures} échecs consécutifs : source indisponible ?"
                    ) from error
                continue
            consecutive_failures = 0
            if response.html is None:
                report.pages_not_modified += 1
                for record in saved.values():
                    if record["page_slug"] == page.slug:
                        count(record)
                        report.unchanged += 1
                continue
            report.pages_downloaded += 1
            records = parse_page(response.html, page, url, now().isoformat(timespec="seconds"))
            if not records:
                report.pages_empty.append(page.slug)
            for record in records:
                count(record)
                previous = saved.get(record["id"])
                if previous is not None and _comparable(previous) == _comparable(record):
                    report.unchanged += 1
                    continue
                _append_line(output_path, record)
                saved[record["id"]] = record
                if previous is None:
                    report.new += 1
                else:
                    report.updated += 1
            if response.etag:
                state[page.slug] = response.etag
                _write_state(state_path, state)  # saved page by page: an interruption loses nothing
    finally:
        report.by_status = dict(statuses)
        report.fields_filled = {name: filled[name] for name in RECORD_FIELDS}

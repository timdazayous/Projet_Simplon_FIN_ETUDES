"""Extract the CERT-FR security advisories from its official JSON API (Issue #42, source 4).

The CERT-FR publishes an OpenAPI-described API (``https://cert.cyber.gouv.fr/openapi.json``):
``GET /avis/json/`` lists every advisory, ``GET /avis/<reference>/json/`` gives one advisory with
structured vendor and product fields. No HTML is parsed.

Steps of :func:`run_extraction`: initialise (read the configuration, read and obey
``robots.txt``, read the advisories already saved), download the list, keep the advisories of
the period that are new or revised since the last run, download each of them, flatten it into a
record, append it to ``data/raw/certfr/avis.jsonl`` (ignored by Git), compact the file (a revised
advisory replaces its older version) and write an execution report.

Respect of the source (not negotiable): ``robots.txt`` is read at start and every URL is checked
against it, the User-Agent names the project and its repository, and there is at most one
request every ``min_interval_seconds`` (never below 2 s). Content: CERT-FR, Licence Ouverte
Etalab 2.0 (the source must be cited by any reuse).

Network access goes through an ``httpx2.Client`` given by the caller, so the tests use a mock
transport and make no network call. A response that does not have the documented structure
raises :class:`ApiFormatError` instead of producing empty fields.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx2
import yaml

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "certfr.yaml"
MIN_ALLOWED_INTERVAL = 2.0  # seconds: the floor of the politeness rule, whatever the config says

# Distinct exit codes (see scripts/fetch_certfr.py).
EXIT_OK = 0
EXIT_PARTIAL = 1
EXIT_CONFIG = 2
EXIT_ROBOTS = 3
EXIT_FORMAT = 4
EXIT_NETWORK = 5

# Same pattern as the OpenAPI description, restricted to the current format.
REFERENCE_RE = re.compile(r"^CERT(?:FR|A)-\d{4}-AVI-\d{2,4}$")
NOT_FILLED = "N/A"  # value used by the API when a vendor or product name is not filled in


# --------------------------------------------------------------------------- errors


class ExtractionError(RuntimeError):
    """Base class of the errors that stop a run. ``exit_code`` and ``status`` feed the report."""

    exit_code = EXIT_NETWORK
    status = "error"


class ConfigError(ExtractionError):
    exit_code = EXIT_CONFIG
    status = "config_error"


class RobotsError(ExtractionError):
    """``robots.txt`` cannot be read, or forbids a path we were about to visit."""

    exit_code = EXIT_ROBOTS
    status = "robots_refused"


class ApiFormatError(ExtractionError):
    """The JSON does not have the documented structure (the API probably changed)."""

    exit_code = EXIT_FORMAT
    status = "format_changed"


class FetchError(ExtractionError):
    """A page could not be downloaded (after the retries)."""

    exit_code = EXIT_NETWORK
    status = "network_error"


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class CertfrConfig:
    base_url: str
    user_agent: str
    min_interval_seconds: float
    timeout_seconds: float
    max_retries: int
    backoff_seconds: float
    max_consecutive_failures: int
    months: int
    output_directory: Path


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> CertfrConfig:
    """Read ``config/certfr.yaml``; refuse a rate faster than one request every 2 seconds."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        config = CertfrConfig(
            base_url=str(raw["base_url"]).rstrip("/"),
            user_agent=str(raw["user_agent"]),
            min_interval_seconds=float(raw["min_interval_seconds"]),
            timeout_seconds=float(raw["timeout_seconds"]),
            max_retries=int(raw["max_retries"]),
            backoff_seconds=float(raw["backoff_seconds"]),
            max_consecutive_failures=int(raw["max_consecutive_failures"]),
            months=int(raw["months"]),
            output_directory=Path(raw["output_directory"]),
        )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
        raise ConfigError(f"Configuration illisible ou incomplète ({path}) : {error!r}") from error
    if config.min_interval_seconds < MIN_ALLOWED_INTERVAL:
        raise ConfigError(
            f"min_interval_seconds={config.min_interval_seconds} : le minimum accepté est "
            f"{MIN_ALLOWED_INTERVAL} s (une requête toutes les 2 secondes au plus)."
        )
    if "github.com" not in config.user_agent:
        raise ConfigError("Le User-Agent doit identifier le projet et son dépôt GitHub.")
    return config


# --------------------------------------------------------------------------- parsing


def _ascii_lower(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _ascii_lower(text)).strip("-")


def api_date(value: Any) -> date | None:
    """``"2026-10-22T00:00:00.000000"`` (or ``"2026-10-22"``) to a date; ``None`` if undefined.

    The API documents ``null`` for an undefined date. Any other unreadable value is an error.
    """
    if value is None or value == "null" or value == "":
        return None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            pass
    raise ApiFormatError(f"Date au format inattendu : {value!r}")


@dataclass(frozen=True)
class ListEntry:
    reference: str
    title: str
    last_revision: date | None
    scada: bool
    url: str


def parse_list(payload: Any, base_url: str) -> list[ListEntry]:
    """Read the advisory list. Raises :class:`ApiFormatError` if it is not the documented array."""
    if not isinstance(payload, list) or not payload:
        raise ApiFormatError("Liste des avis : un tableau non vide était attendu.")
    base_host = urlparse(base_url).hostname
    entries = []
    for item in payload:
        if not isinstance(item, dict):
            raise ApiFormatError("Liste des avis : élément qui n'est pas un objet.")
        reference, title, json_url = item.get("reference"), item.get("title"), item.get("json_url")
        if not isinstance(reference, str) or not REFERENCE_RE.match(reference):
            raise ApiFormatError(f"Liste des avis : référence inattendue {reference!r}.")
        if not isinstance(title, str) or not isinstance(json_url, str):
            raise ApiFormatError(f"Liste des avis : titre ou json_url manquant ({reference}).")
        url = urljoin(base_url + "/", json_url)
        if urlparse(url).hostname != base_host or not urlparse(url).path.startswith("/avis/"):
            raise ApiFormatError(f"Liste des avis : json_url hors de /avis/ ({reference}).")
        entries.append(
            ListEntry(
                reference=reference,
                title=title,
                last_revision=api_date(item.get("last_revision_date")),
                scada=bool(item.get("scada")),
                url=url,
            )
        )
    return entries


_VERSION = r"[0-9][0-9A-Za-z._~+-]*"
_VERSION_PATTERNS = (
    # "Node.js versions 22.x antérieures à 22.23.4"
    # "IOS XE versions 17.12.x et antérieures à 17.12.8"
    re.compile(
        rf"(?:^|\s)versions? (?P<branch>{_VERSION}) (?:et )?antérieures? à (?P<fixed>{_VERSION})$"
    ),
    # "Splunk SOAR versions antérieures à 8.7.0"
    re.compile(rf"(?:^|\s)versions? antérieures? à (?P<fixed>{_VERSION})$"),
)


def parse_version(description: str) -> tuple[str | None, str | None]:
    """Branch and fixed version of one affected-system description, ``(None, None)`` if unsure.

    Conservative on purpose: only the two most frequent phrasings are interpreted. A correction
    with a special patch (« and SMU … »), a lower bound (« postérieures à … ») or any other
    phrasing keeps only the original text, to be refined at the aggregation step.
    """
    text = " ".join(description.split())
    for pattern in _VERSION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.groupdict().get("branch"), match.group("fixed")
    return None, None


def _name(value: Any) -> str | None:
    """A vendor or product name, ``None`` when the API says it is not filled in."""
    if isinstance(value, str) and value.strip() and value.strip() != NOT_FILLED:
        return value.strip()
    return None


def normalize_system(system: Any) -> dict[str, Any]:
    """One ``affected_systems`` object of the API to a flat record."""
    if not isinstance(system, dict) or not isinstance(system.get("description"), str):
        raise ApiFormatError("affected_systems : objet sans description.")
    product = system.get("product")
    product = product if isinstance(product, dict) else {}
    vendor = product.get("vendor")
    vendor = vendor if isinstance(vendor, dict) else {}
    product_name, vendor_name = _name(product.get("name")), _name(vendor.get("name"))
    description = " ".join(system["description"].split())
    branch, fixed = parse_version(description)
    return {
        "description": description,
        "vendor": vendor_name,
        "product": product_name,
        "product_slug": slugify(product_name) if product_name else None,
        "branch": branch,
        "fixed_in": fixed,
        "version_parsed": fixed is not None,
    }


def _list_of(detail: dict[str, Any], key: str, reference: str) -> list[Any]:
    value = detail.get(key)
    if not isinstance(value, list):
        raise ApiFormatError(f"{reference} : le champ « {key} » devrait être une liste.")
    return value


def parse_advisory(detail: Any, entry: ListEntry, extracted_at: str) -> dict[str, Any]:
    """Flatten one advisory of the API into a record.

    Required (otherwise :class:`ApiFormatError`): the keys of the documented schema with the
    right type, the same reference as the list, a non-empty title and summary. The lists may
    legitimately be empty on some advisories.
    """
    if not isinstance(detail, dict):
        raise ApiFormatError(f"{entry.reference} : un objet JSON était attendu.")
    reference = detail.get("reference")
    if reference != entry.reference:
        raise ApiFormatError(
            f"{entry.url} : la réponse décrit {reference!r}, pas {entry.reference}."
        )
    title, summary = detail.get("title"), detail.get("summary")
    if not isinstance(title, str) or not title.strip():
        raise ApiFormatError(f"{reference} : titre absent ou vide.")
    if not isinstance(summary, str) or not summary.strip():
        raise ApiFormatError(f"{reference} : résumé absent ou vide.")

    systems = [normalize_system(s) for s in _list_of(detail, "affected_systems", reference)]
    risks = [r.get("description") for r in _list_of(detail, "risks", reference)]
    cves = [c.get("name") for c in _list_of(detail, "cves", reference)]
    links = _list_of(detail, "links", reference)
    vendor_advisories = _list_of(detail, "vendor_advisories", reference)
    revisions = _list_of(detail, "revisions", reference)
    if not all(isinstance(x, str) for x in risks + cves):
        raise ApiFormatError(f"{reference} : risque ou CVE sans texte.")

    revision_dates = sorted(
        d for d in (api_date(r.get("revision_date")) for r in revisions) if d is not None
    )
    last = entry.last_revision or (revision_dates[-1] if revision_dates else None)
    first = revision_dates[0] if revision_dates else last
    return {
        "reference": reference,
        "title": title.strip(),
        "first_version_date": first.isoformat() if first else None,
        "last_version_date": last.isoformat() if last else None,
        "risks": risks,
        "affected_systems": systems,
        "affected_systems_note": str(detail.get("affected_systems_content") or "").strip(),
        "summary": summary.strip(),
        "cve": sorted(set(cves)),
        "vendor_advisories": [
            {"title": a.get("title"), "url": a.get("url"), "published_at": a.get("published_at")}
            for a in vendor_advisories
        ],
        "links": [{"title": link.get("title"), "url": link.get("url")} for link in links],
        "revisions": [
            {
                "date": (d.isoformat() if (d := api_date(r.get("revision_date"))) else None),
                "description": r.get("description"),
            }
            for r in revisions
        ],
        "scada": entry.scada,
        "url": entry.url,
        "extracted_at": extracted_at,
    }


# --------------------------------------------------------------------------- network


class RateLimiter:
    """Guarantee a minimum delay between two requests (clock and sleep are injectable)."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        if self._last is not None:
            remaining = self.min_interval - (self._clock() - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


class Fetcher:
    """Polite HTTP access: robots.txt check, rate limit, timeout, retries with growing delay."""

    def __init__(
        self,
        client: httpx2.Client,
        config: CertfrConfig,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.client = client
        self.config = config
        self._sleep = sleep
        self.limiter = RateLimiter(config.min_interval_seconds, clock=clock, sleep=sleep)
        self.robots: RobotFileParser | None = None
        self.requests_made = 0

    def load_robots(self) -> None:
        """Read robots.txt (404 means no restriction; any other failure refuses to go on)."""
        url = f"{self.config.base_url}/robots.txt"
        try:
            response = self._request(url)
        except FetchError as error:
            raise RobotsError(f"robots.txt illisible, abandon par prudence : {error}") from error
        parser = RobotFileParser()
        if response.status_code == 404:
            parser.parse([])
        elif response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            raise RobotsError(f"robots.txt : réponse HTTP {response.status_code}, abandon.")
        self.robots = parser

    def get_json(self, url: str) -> Any:
        """Download one JSON document after checking robots.txt."""
        if self.robots is None:
            raise RobotsError("robots.txt n'a pas été lu : appeler load_robots() d'abord.")
        if not self.robots.can_fetch(self.config.user_agent, url):
            raise RobotsError(f"robots.txt interdit {url} : aucune requête envoyée.")
        response = self._request(url)
        if response.status_code != 200:
            raise FetchError(f"{url} : HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise ApiFormatError(f"{url} : la réponse n'est pas du JSON valide.") from error

    def _request(self, url: str) -> httpx2.Response:
        base_host = urlparse(self.config.base_url).hostname
        last_error = "inconnue"
        for attempt in range(self.config.max_retries + 1):
            if attempt:
                self._sleep(self.config.backoff_seconds * 2 ** (attempt - 1))
            self.limiter.wait()
            self.requests_made += 1
            try:
                response = self.client.get(url, headers={"Accept": "application/json"})
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
    """Records of ``avis.jsonl`` by reference; the last line of a reference wins and a truncated
    line (interrupted run) is ignored."""
    records: dict[str, dict[str, Any]] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                records[record["reference"]] = record
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return records


def compact(path: Path) -> None:
    """Rewrite the file with one line per reference (a revised advisory replaces its old line)."""
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


# --------------------------------------------------------------------------- run


@dataclass
class ExtractionReport:
    source: str = "certfr"
    status: str = "ok"
    error: str | None = None
    started_at: str = ""
    duration_seconds: float = 0.0
    requests: int = 0
    list_entries: int = 0
    in_period: int = 0
    outside_period: int = 0
    without_date: int = 0
    up_to_date: int = 0
    revised: int = 0
    avis_written: int = 0
    without_affected_systems: int = 0
    systems_total: int = 0
    systems_with_vendor_and_product: int = 0
    systems_version_parsed: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)


def run_extraction(
    config: CertfrConfig,
    client: httpx2.Client,
    *,
    limit: int | None = None,
    months: int | None = None,
    today: date | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> ExtractionReport:
    """Run the whole extraction. The report is written even when the run stops on an error."""
    started = clock()
    report = ExtractionReport(started_at=now().isoformat(timespec="seconds"))
    output_dir = config.output_directory
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "avis.jsonl"
    fetcher = Fetcher(client, config, sleep=sleep, clock=clock)
    try:
        compact(output_path)  # drop a truncated line left by an interrupted run
        _extract(config, fetcher, report, output_path, limit, months, today, now)
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
            "certfr : %d avis écrits (dont %d révisés), %d à jour, %d requêtes, %.1f s, statut %s",
            report.avis_written,
            report.revised,
            report.up_to_date,
            report.requests,
            report.duration_seconds,
            report.status,
        )
    return report


def _extract(
    config: CertfrConfig,
    fetcher: Fetcher,
    report: ExtractionReport,
    output_path: Path,
    limit: int | None,
    months: int | None,
    today: date | None,
    now: Callable[[], datetime],
) -> None:
    fetcher.load_robots()  # initialisation: nothing is visited before this succeeds
    saved = read_records(output_path)
    cutoff = (today or now().date()) - timedelta(days=round((months or config.months) * 30.4375))

    entries = parse_list(fetcher.get_json(f"{config.base_url}/avis/json/"), config.base_url)
    report.list_entries = len(entries)
    todo: list[tuple[ListEntry, bool]] = []
    for entry in entries:
        if entry.last_revision is None:
            report.without_date += 1  # the period cannot be checked: listed in the report only
            continue
        if entry.last_revision < cutoff:
            report.outside_period += 1
            continue
        report.in_period += 1
        previous = saved.get(entry.reference)
        if previous is None:
            todo.append((entry, False))
        elif (api_date(previous.get("last_version_date")) or date.min) < entry.last_revision:
            todo.append((entry, True))  # revised since the saved version
        else:
            report.up_to_date += 1
    # Newest first, so that --limit keeps the most recent advisories.
    todo.sort(key=lambda item: (item[0].last_revision, item[0].reference), reverse=True)
    if limit is not None:
        todo = todo[:limit]

    consecutive_failures = 0
    for entry, is_revision in todo:
        try:
            detail = fetcher.get_json(entry.url)
        except FetchError as error:
            report.failures.append({"reference": entry.reference, "error": str(error)})
            consecutive_failures += 1
            if consecutive_failures >= config.max_consecutive_failures:
                raise FetchError(
                    f"{consecutive_failures} échecs consécutifs : source indisponible ?"
                ) from error
            continue
        consecutive_failures = 0
        record = parse_advisory(detail, entry, now().isoformat(timespec="seconds"))
        _append_line(output_path, record)
        report.avis_written += 1
        report.revised += is_revision
        systems = record["affected_systems"]
        report.systems_total += len(systems)
        report.systems_with_vendor_and_product += sum(
            bool(s["vendor"] and s["product"]) for s in systems
        )
        report.systems_version_parsed += sum(s["version_parsed"] for s in systems)
        if not systems:
            report.without_affected_systems += 1

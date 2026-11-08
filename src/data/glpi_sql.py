"""Incremental SQL extraction of the GLPI tickets, with pseudonymisation on import (Issue #53).

Steps of :func:`run_extraction`: initialise (find the last extraction date), connect to MariaDB
with the read-only account, read the tickets changed since then (query in ``sql/glpi/``),
read their requesters, convert each row to the common schema (HTML to text, UTC dates,
taxonomy labels, pseudonyms, masking of personal data and secrets), merge the rows into
``data/raw/glpi/tickets.jsonl`` and save a counters-only report. Nothing personal is written
before :class:`~src.data.pseudonymize.Pseudonymizer` has been applied, and no ticket text is
ever logged.

The connection is injected (a factory), so the tests use no database.
"""

from __future__ import annotations

import html
import json
import logging
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymysql
from bs4 import BeautifulSoup
from dotenv import dotenv_values

from src.data.pseudonymize import Pseudonymizer
from src.data.taxonomy import Taxonomy, load_taxonomy

ROOT = Path(__file__).resolve().parents[2]
SQL_DIRECTORY = ROOT / "sql" / "glpi"
OUTPUT_DIRECTORY = ROOT / "data" / "raw" / "glpi"

logger = logging.getLogger("glpi_sql")

# Exit codes of scripts/extract_glpi_sql.py
EXIT_OK = 0
EXIT_CONFIG = 2  # invalid option, missing variable or missing key
EXIT_AUTH = 3  # access denied for the read-only account
EXIT_UNAVAILABLE = 4  # database unreachable after the retries
EXIT_QUERY = 5  # the query failed (missing right, unknown column...)

EPOCH = datetime(1970, 1, 1, 1, 0, 0, tzinfo=UTC)  # first TIMESTAMP value MariaDB accepts
NO_LIMIT = 2_147_483_647
BATCH = 500  # tickets per requester query
REQUIRED_VARIABLES = ("GLPI_DB_READER_USER", "GLPI_DB_READER_PASSWORD")

# GLPI ticket type -> project type. GLPI has no "information" type (see docs/glpi.md).
TYPE_FROM_GLPI = {1: "incident", 2: "service_request"}
# GLPI priority 1..5 -> project priority. The injection only writes 2..5.
PRIORITY_FROM_GLPI = {5: "P1", 4: "P2", 3: "P3", 2: "P4", 1: "P4"}


class SqlConfigError(Exception):
    """Missing variable (names only in the message, never a value)."""


class QueryError(Exception):
    """The database refused or failed a query (not a connection problem)."""


@dataclass(frozen=True)
class SqlConfig:
    host: str
    port: int
    database: str
    user: str = field(repr=False)
    password: str = field(repr=False)
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    max_retries: int = 3
    backoff: float = 2.0


def load_sql_config(env_file: str | Path = ".env") -> SqlConfig:
    """Read the read-only account variables. Only variable names appear in errors."""
    path = Path(env_file)
    if not path.is_file():
        raise SqlConfigError(f"fichier d'environnement introuvable : {path}")
    values = dotenv_values(path)
    missing = [name for name in REQUIRED_VARIABLES if not values.get(name)]
    if missing:
        raise SqlConfigError(f"variables manquantes ou vides : {', '.join(missing)}")
    try:
        port = int(values.get("GLPI_DB_HOST_PORT") or 3307)
    except ValueError as error:
        raise SqlConfigError("GLPI_DB_HOST_PORT doit être un nombre") from error
    return SqlConfig(
        host=str(values.get("GLPI_DB_READER_HOST") or "127.0.0.1"),
        port=port,
        database=str(values.get("GLPI_DB_NAME") or "glpi"),
        user=str(values["GLPI_DB_READER_USER"]),
        password=str(values["GLPI_DB_READER_PASSWORD"]),
    )


def connect(config: SqlConfig) -> Any:
    """Open a read-only session in UTC (the real connection factory)."""
    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        connect_timeout=config.connect_timeout,
        read_timeout=config.read_timeout,
        cursorclass=pymysql.cursors.DictCursor,
        # TIMESTAMP columns are returned in the session time zone: ask for UTC.
        init_command="SET time_zone = '+00:00'",
    )
    # A READ ONLY transaction adds a second barrier to the account's SELECT-only rights.
    # (MariaDB wants it as a statement of its own, not combined with the SET above.)
    with connection.cursor() as cursor:
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
    return connection


def load_query(name: str) -> str:
    """Read a versioned query; comment lines are dropped (they could contain a ``%``)."""
    lines = (SQL_DIRECTORY / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("--")).strip()


# --------------------------------------------------------------------------- conversion


def html_to_text(raw: str | None) -> str:
    """GLPI stores rich text as (sometimes escaped) HTML: return plain text."""
    if not raw:
        return ""
    text = raw
    for _ in range(2):  # GLPI escapes the markup itself (&lt;p&gt;) in many versions
        if "&lt;" in text or "&#60;" in text:
            text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(p|div|li)\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = BeautifulSoup(text, "html.parser").get_text()
    text = html.unescape(text).replace("\r\n", "\n").replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def to_utc_iso(value: datetime | None) -> str | None:
    """Naive datetimes of the session (UTC) -> ISO 8601 with offset."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds")


@dataclass
class ExtractionReport:
    since: str = ""
    full: bool = False
    limit: int | None = None
    explain: bool = False
    rows_read: int = 0
    records_written: int = 0
    records_total: int = 0
    skipped_empty_text: int = 0
    unknown_category: int = 0
    no_category: int = 0
    requesters_read: int = 0
    masked: dict[str, int] = field(default_factory=dict)
    last_date_mod: str | None = None
    retries: int = 0
    auth_failed: bool = False
    unavailable: bool = False
    query_failed: bool = False
    duration_seconds: float = 0.0

    def exit_code(self) -> int:
        if self.auth_failed:
            return EXIT_AUTH
        if self.unavailable:
            return EXIT_UNAVAILABLE
        if self.query_failed:
            return EXIT_QUERY
        return EXIT_OK


def convert_row(
    row: dict[str, Any],
    requesters: list[dict[str, Any]],
    pseudonymizer: Pseudonymizer,
    taxonomy: Taxonomy,
    report: ExtractionReport,
    masked_counts: Counter,
) -> dict[str, Any] | None:
    """Convert one ticket row to the common schema, or return None if it is unusable."""
    names = [f"{r.get('firstname') or ''} {r.get('realname') or ''}".strip() for r in requesters]
    subject = pseudonymizer.mask_text(row.get("name") or "", names)
    body = pseudonymizer.mask_text(html_to_text(row.get("content")), names)
    masked_counts.update(subject.counts)
    masked_counts.update(body.counts)
    if not subject.text.strip() and not body.text.strip():
        report.skipped_empty_text += 1
        return None

    category = row.get("category_code")
    if not category:
        report.no_category += 1
    elif category not in taxonomy.categories:
        report.unknown_category += 1
        category = None

    people = []
    for requester in requesters:
        if requester.get("users_id"):
            people.append(pseudonymizer.pseudonym(requester["users_id"], "person"))
        elif requester.get("alternative_email"):
            people.append(pseudonymizer.pseudonym(requester["alternative_email"], "person"))
    entity = row.get("entity_name")
    return {
        "id": f"GLPI-{row['id']}",
        "source": "glpi",
        "origin_id": str(row["id"]),
        "external_ref": row.get("externalid"),
        "created_at": to_utc_iso(row.get("date")),
        "updated_at": to_utc_iso(row.get("date_mod")),
        "channel": None,  # not stored by the injection (see docs/glpi.md)
        "subject": subject.text,
        "body": body.text,
        "language_source": "fr",
        "category": category,
        "type": TYPE_FROM_GLPI.get(row.get("type")),
        "priority": PRIORITY_FROM_GLPI.get(row.get("priority")),
        "team": None,
        "label_origin": "glpi_input",
        "client": entity if entity and entity != "Root entity" else None,
        "requesters": sorted(set(people)),
        "followup_count": int(row.get("followup_count") or 0),
        "glpi_status": row.get("status"),
    }


# --------------------------------------------------------------------------- database access


def _open_with_retries(
    factory: Callable[[SqlConfig], Any],
    config: SqlConfig,
    report: ExtractionReport,
    sleep: Callable[[float], None],
) -> Any:
    """Connect, retrying with growing waits on connection errors; refuse bad credentials at once."""
    for attempt in range(config.max_retries + 1):
        if attempt:
            report.retries += 1
            sleep(config.backoff * 2 ** (attempt - 1))
        try:
            return factory(config)
        except pymysql.err.OperationalError as error:
            if (
                error.args and error.args[0] == 1045
            ):  # access denied: retrying would lock the account
                report.auth_failed = True
                return None
            logger.warning("Connexion impossible (code %s)", error.args[0] if error.args else "?")
        except pymysql.err.MySQLError as error:  # not a connection problem: do not retry
            report.query_failed = True
            logger.error("Session refusée (code %s)", error.args[0] if error.args else "?")
            return None
    report.unavailable = True
    return None


def _fetch_requesters(cursor: Any, ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    by_ticket: dict[int, list[dict[str, Any]]] = {}
    template = load_query("requesters.sql")
    for start in range(0, len(ids), BATCH):
        chunk = ids[start : start + BATCH]
        # Only "%s" markers are built here; the identifiers are bound by the driver.
        cursor.execute(template.format(ids=", ".join(["%s"] * len(chunk))), chunk)
        for row in cursor.fetchall():
            by_ticket.setdefault(row["tickets_id"], []).append(row)
    return by_ticket


def explain_plans(connection: Any, since: datetime, limit: int) -> str:
    """EXPLAIN of the ticket query (no data is read): the text to keep as C2 evidence."""
    with connection.cursor() as cursor:
        cursor.execute("EXPLAIN " + load_query("tickets.sql"), {"since": since, "limit": limit})
        rows = cursor.fetchall()
    lines = []
    for row in rows:
        lines.append(" | ".join(f"{key}={value}" for key, value in row.items()))
    return "\n".join(lines)


# --------------------------------------------------------------------------- output and state


def read_state(directory: Path) -> datetime | None:
    path = directory / "state.json"
    if not path.exists():
        return None
    try:
        return datetime.fromisoformat(json.loads(path.read_text("utf-8"))["last_date_mod"])
    except (ValueError, KeyError, TypeError):
        return None  # corrupted state: fall back to a full extraction


def write_state(directory: Path, last_date_mod: str) -> None:
    (directory / "state.json").write_text(
        json.dumps({"last_date_mod": last_date_mod}, indent=2), encoding="utf-8"
    )


def merge_records(path: Path, new: list[dict[str, Any]], replace_all: bool) -> int:
    """Upsert by ``id`` into the JSON Lines file (atomic write). Return the total."""
    merged: dict[str, dict[str, Any]] = {}
    if path.exists() and not replace_all:
        with open(path, encoding="utf-8") as handle:
            merged = {r["id"]: r for r in map(json.loads, filter(str.strip, handle))}
    merged.update({r["id"]: r for r in new})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".jsonl.tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        for record in sorted(merged.values(), key=lambda r: int(r["origin_id"])):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(path)
    return len(merged)


# --------------------------------------------------------------------------- run


def run_extraction(
    config: SqlConfig,
    pseudonymizer: Pseudonymizer,
    *,
    since: datetime | None = None,
    full: bool = False,
    limit: int | None = None,
    explain: bool = False,
    output_directory: Path = OUTPUT_DIRECTORY,
    taxonomy: Taxonomy | None = None,
    connection_factory: Callable[[SqlConfig], Any] = connect,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> ExtractionReport:
    """Extract the tickets changed since ``since`` (default: the last extraction)."""
    started = clock()
    taxonomy = taxonomy or load_taxonomy()
    if full:
        start = EPOCH
    else:
        start = since or read_state(output_directory) or EPOCH
    report = ExtractionReport(
        since=start.isoformat(timespec="seconds"), full=full, limit=limit, explain=explain
    )
    connection = _open_with_retries(connection_factory, config, report, sleep)
    if connection is None:
        report.duration_seconds = round(clock() - started, 1)
        return report
    masked_counts: Counter = Counter()
    try:
        if explain:
            plan = explain_plans(connection, start.replace(tzinfo=None), limit or NO_LIMIT)
            output_directory.mkdir(parents=True, exist_ok=True)
            (output_directory / "explain.txt").write_text(plan + "\n", encoding="utf-8")
            report.duration_seconds = round(clock() - started, 1)
            return report
        with connection.cursor() as cursor:
            cursor.execute(
                load_query("tickets.sql"),
                {"since": start.replace(tzinfo=None), "limit": limit or NO_LIMIT},
            )
            rows = cursor.fetchall()
            report.rows_read = len(rows)
            requesters = _fetch_requesters(cursor, [int(r["id"]) for r in rows])
        report.requesters_read = sum(len(v) for v in requesters.values())
        records = []
        for row in rows:
            record = convert_row(
                row, requesters.get(int(row["id"]), []), pseudonymizer, taxonomy, report,
                masked_counts,
            )  # fmt: skip
            if record:
                records.append(record)
        report.records_written = len(records)
        report.masked = dict(masked_counts)
        if rows:
            report.last_date_mod = to_utc_iso(max(r["date_mod"] for r in rows if r["date_mod"]))
        output_directory.mkdir(parents=True, exist_ok=True)
        report.records_total = merge_records(
            output_directory / "tickets.jsonl", records, replace_all=full
        )
        if report.last_date_mod:
            write_state(output_directory, report.last_date_mod)
    except pymysql.err.MySQLError as error:
        report.query_failed = True
        logger.error("Requête refusée ou en échec (code %s)", error.args[0] if error.args else "?")
    finally:
        connection.close()
    report.duration_seconds = round(clock() - started, 1)
    (output_directory / "extraction_report.json").write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report

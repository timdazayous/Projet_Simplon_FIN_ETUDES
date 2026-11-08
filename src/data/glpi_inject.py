"""Inject generated tickets into GLPI through its API v2 (Issue #52).

Steps of :func:`run_injection`: initialise (generate the series of tickets, which is
deterministic for a given seed), build the GLPI reference data (the 12 categories of
``config/taxonomy.yaml`` and one entity per fictitious client, created only when missing),
read the ``external_id`` of the tickets already present, create the missing tickets, save an
execution report (counters only, never ticket content).

Running it twice creates nothing the second time: the original identifier ``GEN-T-...`` is
stored in the GLPI ``external_id`` field and looked up first.
"""

from __future__ import annotations

import html
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.data.generator import generate
from src.data.glpi_api import GlpiApiError, GlpiClient, GlpiUnavailable
from src.data.taxonomy import Taxonomy, load_taxonomy

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = ROOT / "data" / "raw" / "glpi" / "injection_report.json"

logger = logging.getLogger("glpi_inject")

# Exit codes of scripts/inject_glpi.py
EXIT_OK = 0
EXIT_PARTIAL = 1  # some tickets failed, the others were created
EXIT_CONFIG = 2  # invalid option or missing configuration
EXIT_AUTH = 3  # token refused
EXIT_UNAVAILABLE = 4  # GLPI unreachable or overloaded
EXIT_PERMISSION = 5  # the API profile lacks a right (403)
EXIT_ENTITY = 6  # GLPI created an entity but did not store its name (see docs/glpi.md)

# Priority P1..P4 -> GLPI priority (1 very low .. 5 very high). GLPI computes the priority from
# urgency x impact; giving the same value to both returns the diagonal of its default matrix,
# which is exactly this value (checked on the real instance, see docs/glpi.md).
PRIORITY_TO_GLPI = {"P1": 5, "P2": 4, "P3": 3, "P4": 2}
# GLPI knows two ticket types only: 1 incident, 2 request. "information" is a request.
TYPE_TO_GLPI = {"incident": 1, "service_request": 2, "information": 2}
ROOT_ENTITY_ID = 0
EXTERNAL_ID_FILTER = "external_id=like=GEN-T-*"


class EntityNameNotStored(Exception):
    """GLPI answered 201 for a new entity but the entity read back has no name."""


@dataclass
class InjectionReport:
    seed: int = 0
    pool: int = 0
    requested: int = 0
    dry_run: bool = False
    categories_created: int = 0
    categories_existing: int = 0
    entities_created: int = 0
    entities_existing: int = 0
    tickets_created: int = 0
    tickets_already_present: int = 0
    tickets_failed: int = 0
    failure_reasons: dict[str, int] = field(default_factory=dict)
    forbidden: bool = False
    entity_name_lost: bool = False
    entities_enabled: bool = True
    auth_failed: bool = False
    unavailable: bool = False
    token_requests: int = 0
    requests: int = 0
    retries: int = 0
    duration_seconds: float = 0.0

    def exit_code(self) -> int:
        if self.auth_failed:
            return EXIT_AUTH
        if self.forbidden:
            return EXIT_PERMISSION
        if self.entity_name_lost:
            return EXIT_ENTITY
        if self.unavailable:
            return EXIT_UNAVAILABLE
        return EXIT_PARTIAL if self.tickets_failed else EXIT_OK


# --------------------------------------------------------------------------- conversion


def to_glpi_datetime(value: str) -> str:
    """ISO date of the generator (naive, understood as UTC) -> ISO 8601 with offset."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="seconds")


def text_to_html(text: str) -> str:
    """Plain text -> the HTML GLPI stores: escaped, one paragraph per blank-line block."""
    paragraphs = [p for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs)


def ticket_payload(ticket: dict[str, Any], category_id: int, entity_id: int) -> dict[str, Any]:
    """Body of ``POST /Assistance/Ticket`` for one generated ticket."""
    level = PRIORITY_TO_GLPI[ticket["priority"]]
    created = to_glpi_datetime(ticket["created_at"])
    return {
        "name": ticket["subject"],
        "content": text_to_html(ticket["body"]),
        "type": TYPE_TO_GLPI[ticket["type"]],
        "urgency": level,
        "impact": level,
        "priority": level,
        "category": {"id": category_id},
        "entity": {"id": entity_id},
        "external_id": ticket["id"],
        "date": created,
        "date_creation": created,
    }


# --------------------------------------------------------------------------- reference data


def ensure_categories(
    client: GlpiClient, taxonomy: Taxonomy, report: InjectionReport, dry_run: bool
) -> dict[str, int]:
    """Return {taxonomy category -> GLPI id}, creating the missing categories.

    A category is recognised by its ``code`` field (the taxonomy key), so renaming the label
    in GLPI does not create a duplicate.
    """
    existing = {
        item.get("code"): int(item["id"]) for item in client.list_all("/Dropdowns/ITILCategory")
    }
    ids: dict[str, int] = {}
    for code, label in taxonomy.categories.items():
        if code in existing:
            ids[code] = existing[code]
            report.categories_existing += 1
            continue
        report.categories_created += 1
        if dry_run:
            ids[code] = -1
            continue
        payload = {
            "name": label,
            "code": code,
            "comment": "Catégorie de config/taxonomy.yaml",
            "entity": {"id": ROOT_ENTITY_ID},
            "is_recursive": True,
        }
        ids[code] = client.create("/Dropdowns/ITILCategory", payload)
    return ids


def ensure_entities(
    client: GlpiClient, names: list[str], report: InjectionReport, dry_run: bool
) -> dict[str, int]:
    """Return {client name -> GLPI entity id}, creating the missing entities under the root."""
    existing = {
        item["name"]: int(item["id"])
        for item in client.list_all("/Administration/Entity")
        if item.get("name")
    }
    ids: dict[str, int] = {}
    for name in sorted(set(names)):
        if name in existing:
            ids[name] = existing[name]
            report.entities_existing += 1
            continue
        report.entities_created += 1
        if dry_run:
            ids[name] = -1
            continue
        payload = {"name": name, "parent": {"id": ROOT_ENTITY_ID}}
        ids[name] = client.create("/Administration/Entity", payload)
        # Read it back: on the tested instance (GLPI 11.0.11) the name was silently dropped.
        # Stop at the first one rather than create dozens of unnamed entities.
        stored = client.request("GET", f"/Administration/Entity/{ids[name]}").json()
        if stored.get("name") != name:
            raise EntityNameNotStored(ids[name])
    return ids


# --------------------------------------------------------------------------- run


def run_injection(
    client: GlpiClient,
    *,
    seed: int,
    pool: int,
    count: int,
    dry_run: bool = False,
    use_entities: bool = True,
    taxonomy: Taxonomy | None = None,
    report_path: Path | None = DEFAULT_REPORT_PATH,
    clock: Any = time.monotonic,
) -> InjectionReport:
    """Inject the first ``count`` tickets of a series of ``pool`` tickets (fixed seed).

    The identifiers ``GEN-T-xxxxxx`` follow the creation date inside the series, so they only
    stay stable if the series (seed and ``pool``) does not change: ``count`` selects how many
    of them to inject.
    """
    started = clock()
    taxonomy = taxonomy or load_taxonomy()
    report = InjectionReport(
        seed=seed, pool=pool, requested=count, dry_run=dry_run, entities_enabled=use_entities
    )
    tickets, _ = generate(seed=seed, n_tickets=pool, n_alerts=0, taxonomy=taxonomy)
    tickets = tickets[:count]
    try:
        categories = ensure_categories(client, taxonomy, report, dry_run)
        client_names = [t["client_name"] for t in tickets] if use_entities else []
        entities = ensure_entities(client, client_names, report, dry_run)
        present = {
            item.get("external_id")
            for item in client.list_all("/Assistance/Ticket", EXTERNAL_ID_FILTER)
        }
        for ticket in tickets:
            if ticket["id"] in present:
                report.tickets_already_present += 1
                continue
            if dry_run:
                report.tickets_created += 1
                continue
            entity_id = entities.get(ticket["client_name"], ROOT_ENTITY_ID)
            payload = ticket_payload(ticket, categories[ticket["category"]], entity_id)
            try:
                client.create("/Assistance/Ticket", payload)
                report.tickets_created += 1
            except GlpiApiError as error:
                if error.status == 403:
                    raise
                _count_failure(report, f"HTTP {error.status}")
            except GlpiUnavailable:
                _count_failure(report, "indisponible")
    except GlpiApiError as error:
        if error.status != 403:
            raise
        report.forbidden = True
        logger.error("Droit manquant pour le profil de l'utilisateur d'API (HTTP 403)")
    except EntityNameNotStored as error:
        report.entity_name_lost = True
        logger.error("Entité %s créée sans nom : arrêt (voir docs/glpi.md)", error)
    except GlpiUnavailable as error:
        report.unavailable = True
        logger.error("GLPI indisponible : %s", error)
    report.token_requests = client.token_requests
    report.requests = client.requests_made
    report.retries = client.retries
    report.duration_seconds = round(clock() - started, 1)
    if report_path is not None and not dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), "utf-8")
    return report


def _count_failure(report: InjectionReport, reason: str) -> None:
    report.tickets_failed += 1
    report.failure_reasons[reason] = report.failure_reasons.get(reason, 0) + 1

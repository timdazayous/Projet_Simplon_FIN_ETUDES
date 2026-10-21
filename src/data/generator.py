"""Synthetic ticket and monitoring-alert generator (offline, no LLM).

Texts come from phrase templates plus random variations (see ``templates.py``);
labels and routing come from ``config/taxonomy.yaml``; proportions come from
``config/generator.yaml``. The same seed and configuration always produce the
same records. All personal data and secrets are fictitious (see ``fictive.py``).
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.data import templates as tpl
from src.data.fictive import SECRET_MARKER, Client, build_clients, fictive_ip
from src.data.taxonomy import Taxonomy, load_taxonomy

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "generator.yaml"
PRIORITY_TOLERANCE = 0.02  # priority_by_type must reproduce priority_target within 2 points


# --------------------------------------------------------------------------- config


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Read the generator configuration file."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _normalised(weights: dict[str, float]) -> dict[str, float]:
    total = float(sum(weights.values()))
    if total <= 0:
        raise ValueError(f"Weights must have a positive sum: {weights}")
    return {key: value / total for key, value in weights.items()}


def implied_priority_marginal(cfg: dict[str, Any]) -> dict[str, float]:
    """Priority shares implied by the type weights and the per-type priority weights."""
    free = cfg["free_text"]
    type_share = _normalised(free["types"])
    result: dict[str, float] = {}
    for ticket_type, share in type_share.items():
        for priority, weight in _normalised(free["priority_by_type"][ticket_type]).items():
            result[priority] = result.get(priority, 0.0) + share * weight
    return result


def validate_config(cfg: dict[str, Any], taxonomy: Taxonomy) -> None:
    """Fail early if the configuration or the text catalogues disagree with the taxonomy."""
    free, alerts = cfg["free_text"], cfg["alerts"]

    def known(values: Iterable[str], allowed: Iterable[str], what: str) -> None:
        unknown = set(values) - set(allowed)
        if unknown:
            raise ValueError(f"Unknown {what} (not in taxonomy.yaml): {sorted(unknown)}")

    known(free["categories"], taxonomy.categories, "category")
    known(free["types"], taxonomy.types, "type")
    known(free["priority_target"], taxonomy.priorities, "priority")
    known(free["channels"], taxonomy.sources, "channel")
    known(free["channels"], set(taxonomy.sources) - set(taxonomy.monitoring_sources), "channel")
    known(free["priority_by_type"], taxonomy.types, "type")
    for weights in free["priority_by_type"].values():
        known(weights, taxonomy.priorities, "priority")
    for category_list in free["channel_affinity"].values():
        known(category_list, taxonomy.categories, "category")
    known(free["channel_affinity"], free["channels"], "channel")
    known(free["secret_categories"], taxonomy.categories, "category")
    known(alerts["sources"], taxonomy.monitoring_sources, "monitoring source")
    known(alerts["tools"], taxonomy.monitoring_severity, "monitoring tool")
    known(alerts["categories"], taxonomy.categories, "category")
    known(alerts["zabbix_severity"], taxonomy.monitoring_severity["zabbix"], "Zabbix severity")
    known(
        [*alerts["centreon_service_state"], *alerts["centreon_host_state"]],
        taxonomy.monitoring_severity["centreon"],
        "Centreon state",
    )

    # The text catalogues must cover the taxonomy exactly (no label hard-coded elsewhere).
    if set(tpl.TICKET_TEMPLATES) != set(taxonomy.categories):
        raise ValueError("TICKET_TEMPLATES categories differ from taxonomy.yaml")
    for category, by_type in tpl.TICKET_TEMPLATES.items():
        if set(by_type) != set(taxonomy.types):
            raise ValueError(f"TICKET_TEMPLATES[{category}] types differ from taxonomy.yaml")
    known(tpl.URGENCY, taxonomy.priorities, "priority")
    missing = set(taxonomy.priorities) - set(tpl.URGENCY)
    if missing:
        raise ValueError(f"No urgency sentence for priorities {sorted(missing)}")
    known(tpl.ALERT_CHECKS, taxonomy.categories, "category")
    for category in alerts["categories"]:
        if category not in tpl.ALERT_CHECKS:
            raise ValueError(f"No alert check defined for category '{category}'")
    for category, checks in tpl.ALERT_CHECKS.items():
        for check_name, _ in checks:
            matched = taxonomy.category_from_check(check_name)
            if matched not in (None, category):
                raise ValueError(f"Check '{check_name}' would be routed to '{matched}'")
    host_matched = taxonomy.category_from_check(tpl.CENTREON_HOST_CHECK[0])
    if host_matched != "network":
        raise ValueError("The Centreon host check must match the 'network' category")

    gap = max(
        abs(share - _normalised(free["priority_target"]).get(priority, 0.0))
        for priority, share in implied_priority_marginal(cfg).items()
    )
    if gap > PRIORITY_TOLERANCE:
        raise ValueError(f"priority_by_type is {gap:.1%} away from priority_target")


# --------------------------------------------------------------------------- helpers


def _weighted(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), weights=list(weights.values()))[0]


class _Slots(dict):
    """Fills ``{placeholders}`` on demand; a placeholder keeps its value in one message."""

    def __init__(self, rng: random.Random, ctx: dict[str, Any]) -> None:
        super().__init__()
        self.rng, self.ctx = rng, ctx

    def __missing__(self, key: str) -> str:
        if key not in tpl.SLOT_FACTORIES:
            raise KeyError(f"Unknown placeholder {{{key}}}")
        value = tpl.SLOT_FACTORIES[key](self.rng, self.ctx)
        self[key] = value
        return value


def _timestamp(rng: random.Random, cfg: dict[str, Any]) -> datetime:
    start = datetime.fromisoformat(str(cfg["start_date"]))
    return start + timedelta(seconds=rng.randint(0, int(cfg["period_days"]) * 86400 - 1))


def _pii_entries(text: str, candidates: list[tuple[str, str]]) -> list[dict[str, str]]:
    """Fictitious personal values that actually appear in ``text`` (for pseudonymisation tests)."""
    return [{"type": kind, "value": value} for kind, value in candidates if value in text]


# --------------------------------------------------------------------------- free text


def _choose_priority(
    rng: random.Random, cfg: dict[str, Any], taxonomy: Taxonomy, ticket_type: str, escalated: bool
) -> str:
    weights = dict(cfg["free_text"]["priority_by_type"][ticket_type])
    if escalated and len(weights) > 1:
        # An escalation cannot concern the least urgent priority.
        weights.pop(taxonomy.priority_order[-1], None)
    return _weighted(rng, weights)


def _choose_channel_and_category(rng: random.Random, cfg: dict[str, Any]) -> tuple[str, str, bool]:
    free = cfg["free_text"]
    channel = _weighted(rng, free["channels"])
    wrong = rng.random() < free["wrong_channel_rate"]
    affinity: dict[str, list[str]] = free["channel_affinity"]
    attached = {c for cats in affinity.values() for c in cats}
    if channel in affinity:
        natural = set(affinity[channel])
    else:
        natural = set(free["categories"]) - attached
    pool = set(free["categories"]) - natural if wrong else natural
    weights = {c: w for c, w in free["categories"].items() if c in pool}
    return channel, _weighted(rng, weights), wrong


def _compose_body(
    rng: random.Random,
    cfg: dict[str, Any],
    slots: _Slots,
    *,
    channel: str,
    category: str,
    priority: str,
    core: str,
    linked: bool,
    escalated: bool,
    user_full_name: str,
    client_name: str,
) -> str:
    free = cfg["free_text"]
    style = {"internal": "internal", "client_portal": "portal"}.get(channel, "email")
    paragraphs: list[str] = []
    greeting = rng.choice(tpl.GREETINGS[style])
    if greeting:
        paragraphs.append(greeting)

    if linked:
        intro = rng.choice(tpl.LINKED_INTRO)
        tail = rng.choice(tpl.LINKED_ESCALATION if escalated else tpl.LINKED_CALM)
        paragraphs.append((intro + tail).format_map(slots))
    paragraphs.append(core)

    extras = [rng.choice(tpl.URGENCY[priority])]
    if category in free["secret_categories"] and rng.random() < free["secret_rate"]:
        extras.append(rng.choice(tpl.SECRET_SENTENCES).format_map(slots))
    if rng.random() < free["contact_line_rate"]:
        extras.append(rng.choice(tpl.CONTACT_SENTENCES).format_map(slots))
    paragraphs.append(" ".join(extras))

    if style == "email":
        signature = user_full_name if rng.random() < 0.8 else f"{user_full_name}\n{client_name}"
        paragraphs.append(f"{rng.choice(tpl.CLOSINGS)}\n{signature}")
    elif style == "internal":
        paragraphs.append(rng.choice(("Merci !", "Merci d'avance.", "Dites-moi si besoin.")))
    elif rng.random() < 0.5:
        paragraphs.append(user_full_name)
    return "\n\n".join(paragraphs)


def generate_tickets(
    cfg: dict[str, Any], taxonomy: Taxonomy, count: int, seed: int, clients: list[Client]
) -> list[dict[str, Any]]:
    """Generate ``count`` free-text tickets (e-mails, portal forms, internal messages)."""
    free = cfg["free_text"]
    rng = random.Random(f"{seed}:tickets")
    records: list[dict[str, Any]] = []
    for _ in range(count):
        channel, category, wrong = _choose_channel_and_category(rng, cfg)
        ticket_type = _weighted(rng, free["types"])
        linked = channel != "internal" and rng.random() < free["linked_ticket"]["rate"]
        escalated = linked and rng.random() < free["linked_ticket"]["escalated_share"]
        priority = _choose_priority(rng, cfg, taxonomy, ticket_type, escalated)

        linked_priority = None
        ref = None
        if linked:
            ref = f"#{rng.randint(10000, 99999)}"
            if escalated:
                order = taxonomy.priority_order
                linked_priority = rng.choice(order[order.index(priority) + 1 :])
            else:
                linked_priority = priority

        client = rng.choice(clients)
        user = rng.choice(client.users)
        slots = _Slots(rng, {"client": client, "user": user, "ref": ref})
        subject_template, body_template = rng.choice(tpl.TICKET_TEMPLATES[category][ticket_type])
        subject = subject_template.format_map(slots)
        core = body_template.format_map(slots)
        if priority in ("P1", "P2") and rng.random() < free["subject_urgent_prefix_rate"]:
            subject = rng.choice(tpl.SUBJECT_PREFIXES_URGENT) + subject
        if linked:
            subject = f"RE: [Ticket {ref}] {subject}"
        elif rng.random() < free["forwarded_rate"]:
            subject = f"TR : {subject}"

        body = _compose_body(
            rng,
            cfg,
            slots,
            channel=channel,
            category=category,
            priority=priority,
            core=core,
            linked=linked,
            escalated=escalated,
            user_full_name=user.full_name,
            client_name=client.name,
        )
        text = f"{subject}\n{body}"
        candidates = [("person", user.full_name), ("email", user.email), ("phone", user.phone)]
        candidates += [(k, slots[k]) for k in ("ip", "secret") if k in slots]
        records.append(
            {
                "created_at": _timestamp(rng, cfg).isoformat(timespec="seconds"),
                "source": channel,
                "subject": subject,
                "body": body,
                "language": "fr",
                "client_id": client.client_id,
                "client_name": client.name,
                "requester": {"name": user.full_name, "email": user.email},
                "category": category,
                "type": ticket_type,
                "priority": priority,
                "team": taxonomy.route_team(category, ticket_type, priority),
                "wrong_channel": wrong,
                "linked_ticket_ref": ref,
                "linked_ticket_priority": linked_priority,
                "priority_escalation": escalated,
                "contains_secret": "secret" in slots,
                "pii": _pii_entries(text, candidates),
                "origin": "synthetic",
            }
        )
    return _number(records, "GEN-T")


# --------------------------------------------------------------------------- alerts


def _alert_numbers(rng: random.Random) -> dict[str, str]:
    return {
        "pct": str(rng.randint(1, 95)),
        "gb": str(rng.randint(1, 40)),
        "n": str(rng.randint(1, 59)),
    }


def _zabbix_text(
    check: str, host: str, ip: str, severity: str, output: str, when: datetime, rng: random.Random
) -> str:
    return (
        f"Problem started at {when:%H:%M:%S} on {when:%Y.%m.%d}\n"
        f"Problem name: {check}\n"
        f"Host: {host}\n"
        f"Host IP: {ip}\n"
        f"Severity: {severity}\n"
        f"Operational data: {output}\n"
        f"Original problem ID: {rng.randint(100000, 999999)}"
    )


def _centreon_text(
    check: str, host: str, ip: str, state: str, output: str, when: datetime, is_host: bool
) -> str:
    lines = [
        "***** Centreon Notification *****",
        "Notification Type: PROBLEM",
        f"Host: {host}",
        f"Address: {ip}",
    ]
    if not is_host:
        lines.append(f"Service: {check}")
    lines += [
        f"State: {state}",
        f"Date/Time: {when:%a %b %d %H:%M:%S %Y}",
        f"Additional Info: {output}",
    ]
    return "\n".join(lines)


def generate_alerts(
    cfg: dict[str, Any], taxonomy: Taxonomy, count: int, seed: int, clients: list[Client]
) -> list[dict[str, Any]]:
    """Generate ``count`` Zabbix / Centreon alerts, labelled by the taxonomy rules."""
    al = cfg["alerts"]
    rng = random.Random(f"{seed}:alerts")
    records: list[dict[str, Any]] = []
    for _ in range(count):
        source = _weighted(rng, al["sources"])
        tool = _weighted(rng, al["tools"])
        client = rng.choice(clients)
        slots = _Slots(rng, {"client": client, "user": client.users[0], "ref": None})
        host, ip = slots["host"], fictive_ip(rng)
        when = _timestamp(rng, cfg)

        is_host = tool == "centreon" and rng.random() < al["centreon_host_state_rate"]
        if is_host:
            category = "network"
            check, output_template = tpl.CENTREON_HOST_CHECK
            severity = _weighted(rng, al["centreon_host_state"])
        else:
            category = _weighted(rng, al["categories"])
            check, output_template = rng.choice(tpl.ALERT_CHECKS[category])
            severity = _weighted(
                rng, al["zabbix_severity"] if tool == "zabbix" else al["centreon_service_state"]
            )
        output = output_template.format(ip=ip, **_alert_numbers(rng))

        if tool == "zabbix":
            body = _zabbix_text(check, host, ip, severity, output, when, rng)
            subject = f"Problem: {check}" if source == "monitoring_email" else f"{host}: {check}"
            if source == "monitoring_email":
                subject = f"[Zabbix] {subject}"
        else:
            body = _centreon_text(check, host, ip, severity, output, when, is_host)
            kind = "Host" if is_host else "Service"
            target = host if is_host else f"{host}/{check}"
            subject = f"** PROBLEM {kind} Alert: {target} is {severity} **"

        priority = taxonomy.monitoring_priority(tool, severity)
        records.append(
            {
                "created_at": when.isoformat(timespec="seconds"),
                "source": source,
                "tool": tool,
                "subject": subject,
                "body": body,
                "client_id": client.client_id,
                "client_name": client.name,
                "host": host,
                "ip": ip,
                "check_name": check,
                "entity": "host" if is_host else "service",
                "tool_severity": severity,
                "category": category,
                "type": "incident",
                "priority": priority,
                "team": taxonomy.route_team(category, "incident", priority),
                "rule_match": taxonomy.category_from_check(check) is not None,
                "pii": _pii_entries(f"{subject}\n{body}", [("ip", ip)]),
                "origin": "synthetic",
            }
        )
    return _number(records, "GEN-A")


# --------------------------------------------------------------------------- entry points


def _number(records: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    """Sort by creation date and give each record a stable identifier."""
    records.sort(key=lambda r: r["created_at"])
    return [{"id": f"{prefix}-{i:06d}", **record} for i, record in enumerate(records, start=1)]


def generate(
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    *,
    seed: int | None = None,
    n_tickets: int | None = None,
    n_alerts: int | None = None,
    taxonomy: Taxonomy | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate (tickets, alerts). Arguments override the configuration file."""
    cfg = load_config(config_path)
    taxonomy = taxonomy or load_taxonomy()
    validate_config(cfg, taxonomy)
    seed = cfg["seed"] if seed is None else seed
    n_tickets = cfg["volumes"]["free_text"] if n_tickets is None else n_tickets
    n_alerts = cfg["volumes"]["alerts"] if n_alerts is None else n_alerts
    clients = build_clients(
        random.Random(f"{seed}:clients"),
        cfg["clients"]["count"],
        cfg["clients"]["users_per_client"],
    )
    tickets = generate_tickets(cfg, taxonomy, n_tickets, seed, clients)
    alerts = generate_alerts(cfg, taxonomy, n_alerts, seed, clients)
    return tickets, alerts


def write_jsonl(path: str | Path, records: Iterable[dict[str, Any]]) -> int:
    """Write one JSON object per line (UTF-8, accents kept). Returns the number of lines."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file written by :func:`write_jsonl`."""
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


__all__ = [
    "SECRET_MARKER",
    "generate",
    "generate_alerts",
    "generate_tickets",
    "implied_priority_marginal",
    "load_config",
    "read_jsonl",
    "validate_config",
    "write_jsonl",
]

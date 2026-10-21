"""Tests of the synthetic ticket and alert generator (Issue #26)."""

from __future__ import annotations

import copy
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from src.data import templates as tpl
from src.data.fictive import (
    DOCUMENTATION_IP_PREFIXES,
    EMAIL_DOMAIN_SUFFIX,
    FICTIVE_PHONE_PREFIXES,
    SECRET_MARKER,
    ascii_slug,
    build_clients,
)
from src.data.generator import (
    generate,
    implied_priority_marginal,
    load_config,
    read_jsonl,
    validate_config,
    write_jsonl,
)
from src.data.taxonomy import load_taxonomy

FIXTURES = Path(__file__).parent / "fixtures"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
IP_RE = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
PHONE_RE = re.compile(r"\b0\d(?: \d{2}){4}\b")


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy()


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def corpus(taxonomy):
    """The default corpus (about 2 400 texts and 1 500 alerts), generated once."""
    return generate(taxonomy=taxonomy)


@pytest.fixture(scope="module")
def tickets(corpus):
    return corpus[0]


@pytest.fixture(scope="module")
def alerts(corpus):
    return corpus[1]


def share(records, predicate) -> float:
    return sum(1 for r in records if predicate(r)) / len(records)


# ----------------------------------------------------------------- volumes, reproducibility


def test_default_volumes(tickets, alerts, cfg):
    assert len(tickets) == cfg["volumes"]["free_text"] == 2400
    assert len(alerts) == cfg["volumes"]["alerts"] == 1500


def test_same_seed_gives_identical_output(taxonomy):
    first = generate(seed=123, n_tickets=200, n_alerts=100, taxonomy=taxonomy)
    second = generate(seed=123, n_tickets=200, n_alerts=100, taxonomy=taxonomy)
    assert first == second


def test_different_seed_gives_different_output(taxonomy):
    first = generate(seed=1, n_tickets=100, n_alerts=50, taxonomy=taxonomy)
    second = generate(seed=2, n_tickets=100, n_alerts=50, taxonomy=taxonomy)
    assert first != second


def test_alerts_do_not_depend_on_the_ticket_count(taxonomy):
    _, alerts_a = generate(seed=5, n_tickets=10, n_alerts=40, taxonomy=taxonomy)
    _, alerts_b = generate(seed=5, n_tickets=300, n_alerts=40, taxonomy=taxonomy)
    assert alerts_a == alerts_b


def test_identical_files_on_disk(tmp_path, taxonomy):
    for name in ("a", "b"):
        tickets, alerts = generate(seed=9, n_tickets=50, n_alerts=20, taxonomy=taxonomy)
        write_jsonl(tmp_path / f"{name}_t.jsonl", tickets)
        write_jsonl(tmp_path / f"{name}_a.jsonl", alerts)
    assert (tmp_path / "a_t.jsonl").read_bytes() == (tmp_path / "b_t.jsonl").read_bytes()
    assert (tmp_path / "a_a.jsonl").read_bytes() == (tmp_path / "b_a.jsonl").read_bytes()


def test_ids_are_unique_and_records_sorted_by_date(tickets, alerts):
    for records in (tickets, alerts):
        assert len({r["id"] for r in records}) == len(records)
        dates = [r["created_at"] for r in records]
        assert dates == sorted(dates)


def test_jsonl_roundtrip(tmp_path, tickets):
    path = tmp_path / "out" / "tickets.jsonl"
    assert write_jsonl(path, tickets[:20]) == 20
    assert read_jsonl(path) == tickets[:20]


# ----------------------------------------------------------------- labels and routing


def test_labels_belong_to_the_taxonomy(tickets, alerts, taxonomy):
    for record in [*tickets, *alerts]:
        assert record["category"] in taxonomy.categories
        assert record["type"] in taxonomy.types
        assert record["priority"] in taxonomy.priorities
        assert record["team"] in taxonomy.teams
    assert {r["source"] for r in tickets} <= set(taxonomy.sources) - set(
        taxonomy.monitoring_sources
    )
    assert {r["source"] for r in alerts} <= set(taxonomy.monitoring_sources)


def test_every_category_and_type_is_covered(tickets, taxonomy):
    assert {r["category"] for r in tickets} == set(taxonomy.categories)
    assert {r["type"] for r in tickets} == set(taxonomy.types)
    assert {r["priority"] for r in tickets} == set(taxonomy.priorities)


def test_team_comes_from_routing_rules(tickets, alerts, taxonomy):
    for record in [*tickets, *alerts]:
        expected = taxonomy.route_team(record["category"], record["type"], record["priority"])
        assert record["team"] == expected


def test_p1_is_only_generated_for_incidents(tickets):
    assert all(r["type"] == "incident" for r in tickets if r["priority"] == "P1")


# ----------------------------------------------------------------- proportions


def test_priority_matrix_reproduces_the_target(cfg):
    marginal = implied_priority_marginal(cfg)
    assert marginal["P1"] == pytest.approx(0.05, abs=0.005)
    assert marginal["P2"] == pytest.approx(0.20, abs=0.01)
    assert marginal["P3"] == pytest.approx(0.45, abs=0.01)
    assert marginal["P4"] == pytest.approx(0.30, abs=0.01)


def test_free_text_proportions(tickets):
    types = Counter(r["type"] for r in tickets)
    n = len(tickets)
    assert types["incident"] / n == pytest.approx(0.55, abs=0.03)
    assert types["service_request"] / n == pytest.approx(0.30, abs=0.03)
    assert types["information"] / n == pytest.approx(0.15, abs=0.03)

    priorities = Counter(r["priority"] for r in tickets)
    for priority, expected in {"P1": 0.05, "P2": 0.20, "P3": 0.45, "P4": 0.30}.items():
        assert priorities[priority] / n == pytest.approx(expected, abs=0.04)

    # Channels: weights 25 / 10 / 5 / 5 among the free-text channels.
    sources = Counter(r["source"] for r in tickets)
    assert sources["support_email"] / n == pytest.approx(25 / 45, abs=0.04)
    assert sources["client_portal"] / n == pytest.approx(10 / 45, abs=0.04)
    assert sources["admin_email"] / n == pytest.approx(5 / 45, abs=0.04)
    assert sources["internal"] / n == pytest.approx(5 / 45, abs=0.04)


def test_wrong_channel_share(tickets):
    assert share(tickets, lambda r: r["wrong_channel"]) == pytest.approx(0.10, abs=0.025)


def test_linked_ticket_shares(tickets):
    clients_messages = [r for r in tickets if r["source"] != "internal"]
    linked = [r for r in clients_messages if r["linked_ticket_ref"]]
    assert len(linked) / len(clients_messages) == pytest.approx(0.15, abs=0.03)
    escalated = [r for r in linked if r["priority_escalation"]]
    assert len(escalated) / len(linked) == pytest.approx(1 / 3, abs=0.07)
    assert not [r for r in tickets if r["source"] == "internal" and r["linked_ticket_ref"]]


def test_alert_proportions(alerts):
    sources = Counter(r["source"] for r in alerts)
    n = len(alerts)
    assert sources["monitoring_connector"] / n == pytest.approx(40 / 55, abs=0.04)
    assert sources["monitoring_email"] / n == pytest.approx(15 / 55, abs=0.04)
    tools = Counter(r["tool"] for r in alerts)
    assert tools["zabbix"] / n == pytest.approx(0.6, abs=0.04)
    assert {r["tool"] for r in alerts} == {"zabbix", "centreon"}


# ----------------------------------------------------------------- special cases


def test_wrong_channel_messages_do_not_fit_their_channel(tickets):
    wrong = [r for r in tickets if r["wrong_channel"]]
    assert wrong
    admin = {"admin_billing", "procurement"}
    for record in wrong:
        if record["source"] == "admin_email":
            assert record["category"] not in admin  # a breakdown sent to the admin mailbox
        else:
            assert record["category"] in admin  # a billing question sent to the support
    normal_admin = [r for r in tickets if r["source"] == "admin_email" and not r["wrong_channel"]]
    assert normal_admin
    assert all(r["category"] in admin for r in normal_admin)


def test_linked_messages_reference_a_ticket_and_urgent_ones_are_more_urgent(tickets, taxonomy):
    order = taxonomy.priority_order
    linked = [r for r in tickets if r["linked_ticket_ref"]]
    assert linked
    for record in linked:
        assert record["linked_ticket_ref"] in record["subject"]
        assert record["linked_ticket_ref"] in record["body"]
        rank = order.index(record["priority"])
        linked_rank = order.index(record["linked_ticket_priority"])
        if record["priority_escalation"]:
            assert rank < linked_rank
        else:
            assert rank == linked_rank
    assert any(r["priority_escalation"] for r in linked)
    assert not [r for r in tickets if not r["linked_ticket_ref"] and r["priority_escalation"]]


def test_special_cases_are_present(tickets):
    assert any(r["wrong_channel"] for r in tickets)
    assert any(r["priority_escalation"] for r in tickets)
    assert any(r["contains_secret"] for r in tickets)
    assert {"incident", "service_request", "information"} == {r["type"] for r in tickets}
    # Each category appears with each type at least once.
    pairs = {(r["category"], r["type"]) for r in tickets}
    assert len(pairs) == 12 * 3


def test_texts_are_french_and_varied(tickets):
    assert all(r["language"] == "fr" and r["subject"] and r["body"] for r in tickets)
    assert len({r["body"] for r in tickets}) > 0.95 * len(tickets)
    assert len({r["subject"] for r in tickets}) > 50


# ----------------------------------------------------------------- alerts


def test_alert_priority_comes_from_the_severity_mapping(alerts, taxonomy):
    for record in alerts:
        assert record["type"] == "incident"
        assert record["priority"] == taxonomy.monitoring_priority(
            record["tool"], record["tool_severity"]
        )


def test_alert_category_is_consistent_with_check_keywords(alerts, taxonomy):
    for record in alerts:
        matched = taxonomy.category_from_check(record["check_name"])
        assert record["rule_match"] == (matched is not None)
        if matched is not None:
            assert record["category"] == matched


def test_alerts_without_rule_exist_but_are_a_minority(alerts):
    unmatched = share(alerts, lambda r: not r["rule_match"])
    assert 0.03 < unmatched < 0.25


def test_alert_text_mentions_its_fields(alerts):
    for record in alerts:
        text = f"{record['subject']}\n{record['body']}"
        assert record["host"] in text
        assert record["tool_severity"] in text
        assert record["ip"] in record["body"]
        if record["tool"] == "zabbix":
            assert record["check_name"] in record["body"]
        elif record["entity"] == "service":
            assert f"Service: {record['check_name']}" in record["body"]
    assert {r["entity"] for r in alerts if r["tool"] == "centreon"} == {"host", "service"}
    host_states = {r["tool_severity"] for r in alerts if r["entity"] == "host"}
    assert host_states <= {"DOWN", "UNREACHABLE"}


# ----------------------------------------------------------------- fictitious data


def test_personal_data_is_fictitious(tickets, alerts):
    for record in [*tickets, *alerts]:
        text = f"{record['subject']}\n{record['body']}"
        for email in EMAIL_RE.findall(text):
            assert email.endswith(EMAIL_DOMAIN_SUFFIX), email
        for ip in IP_RE.findall(text):
            assert ip.startswith(DOCUMENTATION_IP_PREFIXES), ip
        for phone in PHONE_RE.findall(text):
            assert phone.startswith(FICTIVE_PHONE_PREFIXES), phone
    for record in tickets:
        assert record["requester"]["email"].endswith(EMAIL_DOMAIN_SUFFIX)


def test_pii_entries_are_findable_in_the_text(tickets, alerts):
    kinds = Counter()
    for record in [*tickets, *alerts]:
        text = f"{record['subject']}\n{record['body']}"
        for entry in record["pii"]:
            assert entry["value"] in text
            kinds[entry["type"]] += 1
    assert {"person", "email", "phone", "ip", "secret"} <= set(kinds)


def test_secrets_are_marked_fake(tickets):
    flagged = [r for r in tickets if r["contains_secret"]]
    assert flagged
    for record in flagged:
        secrets = [e["value"] for e in record["pii"] if e["type"] == "secret"]
        assert secrets and all(SECRET_MARKER in s for s in secrets)
    assert all(
        not any(e["type"] == "secret" for e in r["pii"])
        for r in tickets
        if not r["contains_secret"]
    )


def test_clients_are_distinct_and_use_test_domains():
    clients = build_clients(random.Random(0), count=60, users_per_client=6)
    assert len(clients) == 60
    assert len({c.name for c in clients}) == 60
    assert len({c.domain for c in clients}) == 60
    for client in clients:
        assert client.domain.endswith(EMAIL_DOMAIN_SUFFIX)
        assert len({u.email for u in client.users}) == 6
        assert all(u.email.endswith(client.domain) for u in client.users)


def test_too_many_clients_is_rejected():
    with pytest.raises(ValueError, match="At most"):
        build_clients(random.Random(0), count=1000)


def test_ascii_slug():
    assert ascii_slug("Élodie Pâquerette") == "elodie-paquerette"


# ----------------------------------------------------------------- templates and config


def test_all_templates_render_without_unknown_placeholder(taxonomy):
    clients = build_clients(random.Random(3), count=5)
    rng = random.Random(4)
    from src.data.generator import _Slots

    for by_type in tpl.TICKET_TEMPLATES.values():
        for entries in by_type.values():
            for subject, body in entries:
                ctx = {"client": clients[0], "user": clients[0].users[0], "ref": "#12345"}
                slots = _Slots(rng, ctx)
                assert "{" not in subject.format_map(slots)
                assert "{" not in body.format_map(slots)
    slots = _Slots(rng, {"client": clients[0], "user": clients[0].users[0], "ref": "#1"})
    with pytest.raises(KeyError):
        "{unknown_slot}".format_map(slots)
    for text in (*tpl.LINKED_INTRO, *tpl.LINKED_CALM, *tpl.LINKED_ESCALATION):
        assert "{" not in text.format_map(slots)
    for text in (*tpl.SECRET_SENTENCES, *tpl.CONTACT_SENTENCES):
        assert "{" not in text.format_map(slots)


def test_templates_cover_the_taxonomy(taxonomy):
    assert set(tpl.TICKET_TEMPLATES) == set(taxonomy.categories)
    for by_type in tpl.TICKET_TEMPLATES.values():
        assert set(by_type) == set(taxonomy.types)
    assert set(tpl.URGENCY) == set(taxonomy.priorities)


def test_validate_config_accepts_the_default_file(cfg, taxonomy):
    validate_config(cfg, taxonomy)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c["free_text"]["categories"].update({"made_up": 1}),
        lambda c: c["free_text"]["types"].update({"made_up": 1}),
        lambda c: c["free_text"]["channels"].update({"monitoring_email": 1}),
        lambda c: c["alerts"]["zabbix_severity"].update({"Catastrophe": 1}),
        lambda c: c["alerts"]["tools"].update({"nagios": 1}),
        lambda c: c["free_text"]["priority_by_type"]["incident"].update({"P1": 80}),
    ],
)
def test_validate_config_rejects_bad_values(cfg, taxonomy, mutate):
    bad = copy.deepcopy(cfg)
    mutate(bad)
    with pytest.raises(ValueError):
        validate_config(bad, taxonomy)


def test_validate_config_rejects_templates_out_of_sync(cfg, taxonomy, monkeypatch):
    broken = {k: v for k, v in tpl.TICKET_TEMPLATES.items() if k != "network"}
    monkeypatch.setattr(tpl, "TICKET_TEMPLATES", broken)
    with pytest.raises(ValueError, match="TICKET_TEMPLATES"):
        validate_config(cfg, taxonomy)


def test_validate_config_rejects_alert_check_with_wrong_keyword(cfg, taxonomy, monkeypatch):
    checks = {**tpl.ALERT_CHECKS, "messaging": [("Mail disk is full", "x")]}
    monkeypatch.setattr(tpl, "ALERT_CHECKS", checks)
    with pytest.raises(ValueError, match="routed to"):
        validate_config(cfg, taxonomy)


# ----------------------------------------------------------------- sample and script


def test_versioned_samples_are_valid(taxonomy):
    tickets = read_jsonl(FIXTURES / "synthetic_tickets_sample.jsonl")
    alerts = read_jsonl(FIXTURES / "synthetic_alerts_sample.jsonl")
    assert 20 <= len(tickets) <= 200 and 20 <= len(alerts) <= 200
    for record in [*tickets, *alerts]:
        assert record["category"] in taxonomy.categories
        assert record["type"] in taxonomy.types
        assert record["priority"] in taxonomy.priorities
        assert record["team"] == taxonomy.route_team(
            record["category"], record["type"], record["priority"]
        )
        assert record["origin"] == "synthetic"


def test_script_writes_both_files(tmp_path):
    script = Path(__file__).resolve().parent.parent / "scripts" / "generate_synthetic.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--tickets",
            "30",
            "--alerts",
            "10",
            "--out-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    assert "30 tickets" in result.stdout
    assert len(read_jsonl(tmp_path / "synthetic_tickets.jsonl")) == 30
    assert len(read_jsonl(tmp_path / "synthetic_alerts.jsonl")) == 10

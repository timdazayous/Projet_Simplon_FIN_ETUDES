"""Tests of the per-category generation used by the corpus assembly (Issue #46)."""

from __future__ import annotations

from collections import Counter

import pytest

from src.data import templates as tpl
from src.data.generator import generate, load_config
from src.data.taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy()


def share(records, predicate) -> float:
    return sum(1 for r in records if predicate(r)) / len(records)


def test_category_counts_are_exact_and_reproducible(taxonomy):
    counts = {"backup": 30, "procurement": 20, "messaging": 10}
    first, _ = generate(seed=3, n_alerts=0, taxonomy=taxonomy, category_counts=counts)
    second, _ = generate(seed=3, n_alerts=0, taxonomy=taxonomy, category_counts=counts)
    assert first == second
    assert Counter(r["category"] for r in first) == counts
    assert len({r["id"] for r in first}) == 60


def test_category_counts_ignore_the_ticket_count_and_keep_alerts_independent(taxonomy):
    tickets, alerts = generate(
        seed=3, n_tickets=999, n_alerts=15, taxonomy=taxonomy, category_counts={"backup": 5}
    )
    assert len(tickets) == 5 and len(alerts) == 15
    _, other_alerts = generate(seed=3, n_alerts=15, taxonomy=taxonomy)
    assert alerts == other_alerts


def test_category_counts_reject_unknown_category(taxonomy):
    with pytest.raises(ValueError, match="Unknown category"):
        generate(seed=3, n_alerts=0, taxonomy=taxonomy, category_counts={"inconnue": 1})


def test_category_counts_follow_channel_affinity(taxonomy):
    tickets, _ = generate(
        seed=4,
        n_alerts=0,
        taxonomy=taxonomy,
        category_counts={"procurement": 300, "network": 300},
    )
    wrong = load_config()["free_text"]["wrong_channel_rate"]
    procurement = [r for r in tickets if r["category"] == "procurement"]
    network = [r for r in tickets if r["category"] == "network"]
    assert share(procurement, lambda r: r["source"] == "admin_email") > 1 - wrong - 0.06
    assert share(network, lambda r: r["source"] == "admin_email") < wrong + 0.06
    assert all(r["wrong_channel"] == (r["source"] == "admin_email") for r in network)


def test_ticket_id_prefix_is_configurable(taxonomy):
    tickets, _ = generate(
        seed=5, n_alerts=0, taxonomy=taxonomy, category_counts={"backup": 3}, ticket_id_prefix="X"
    )
    assert [r["id"] for r in tickets] == ["X-000001", "X-000002", "X-000003"]


def test_extra_templates_widen_the_phrase_pool_of_rare_categories():
    for category in ("messaging", "accounts", "printing", "backup", "telephony", "procurement"):
        by_type = tpl.TICKET_TEMPLATES[category]
        assert sum(len(v) for v in by_type.values()) >= 10, category
        subjects = [s for v in by_type.values() for s, _ in v]
        assert len(subjects) == len(set(subjects)), "duplicate subject template"

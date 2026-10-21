"""Tests of the label-mapping proposal for public datasets."""

from __future__ import annotations

import pytest
import yaml

from src.data.label_mapping import LabelMapping, load_mapping
from src.data.taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def mapping() -> LabelMapping:
    return load_mapping()


def test_real_mapping_only_uses_taxonomy_labels(mapping):
    taxonomy = load_taxonomy()
    for spec in mapping.rules.values():
        for rule in spec.get("category_rules", []):
            assert rule["category"] in taxonomy.categories


def test_customer_support_tags_give_a_category_type_and_priority(mapping):
    proposal = mapping.propose(
        "customer_support",
        {"tags": ["Performance", "Network", "IT"], "type": "Incident", "priority": "high"},
        subject="Slow connection",
    )
    assert (proposal.category, proposal.type, proposal.priority) == ("network", "incident", "P2")
    assert proposal.rule == "network"
    assert not proposal.doubtful


def test_first_matching_rule_wins(mapping):
    # security comes before network in the rule list
    proposal = mapping.propose("customer_support", {"tags": ["Network", "Security"]})
    assert proposal.category == "security"


def test_keyword_in_subject_matches(mapping):
    proposal = mapping.propose(
        "customer_support", {"tags": ["Performance"]}, subject="Drucker defekt"
    )
    assert proposal.category == "printing"


def test_generic_tags_stay_unmapped(mapping):
    proposal = mapping.propose("customer_support", {"tags": ["Tech Support", "IT", "Performance"]})
    assert proposal.category is None
    assert proposal.rule is None


def test_generic_outage_rule_is_flagged_doubtful(mapping):
    proposal = mapping.propose("customer_support", {"tags": ["Outage"]})
    assert proposal.category == "infrastructure"
    assert proposal.doubtful


def test_problem_and_change_types_and_missing_critical_priority(mapping):
    assert mapping.propose("customer_support", {"tags": [], "type": "Problem"}).type == "incident"
    assert (
        mapping.propose("customer_support", {"tags": [], "type": "Change"}).type
        == "service_request"
    )
    priorities = {
        mapping.propose("customer_support", {"tags": [], "priority": p}).priority
        for p in ("low", "medium", "high")
    }
    assert priorities == {"P4", "P3", "P2"}  # P1 is never proposed


@pytest.mark.parametrize(
    ("label", "category", "doubtful"),
    [
        ("Active Directory", "accounts", False),
        ("O365", "messaging", False),
        ("Fileservice", "infrastructure", True),
        ("EOL", None, False),
        ("Support general", None, False),
    ],
)
def test_it_support_labels(mapping, label, category, doubtful):
    proposal = mapping.propose("it_support", {"label": label})
    assert proposal.category == category
    assert proposal.doubtful is doubtful


def test_urgency_dataset_has_no_category(mapping):
    assert mapping.propose("support_urgency", {"expected": "urgent"}).category is None


def test_unknown_dataset_gives_an_empty_proposal(mapping):
    assert mapping.propose("other", {"label": "x"}).category is None


def test_load_mapping_rejects_labels_outside_the_taxonomy(tmp_path):
    bad = {"it_support": {"category": {"O365": "not_a_category"}}}
    path = tmp_path / "mapping.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown category"):
        load_mapping(path)

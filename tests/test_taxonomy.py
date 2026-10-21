"""Tests of the taxonomy loader and of the routing rules."""

from __future__ import annotations

import pytest
import yaml

from src.data.taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy()


def test_taxonomy_has_expected_sizes(taxonomy):
    assert len(taxonomy.categories) == 12
    assert len(taxonomy.types) == 3
    assert list(taxonomy.priorities) == ["P1", "P2", "P3", "P4"]
    assert len(taxonomy.teams) == 6


@pytest.mark.parametrize(
    ("category", "ticket_type", "priority", "team"),
    [
        ("security", "incident", "P4", "security"),  # rule 1 wins over everything
        ("procurement", "information", "P3", "procurement"),
        ("admin_billing", "incident", "P1", "account_management"),
        ("network", "incident", "P1", "systems_network"),  # P1 + incident
        ("printing", "incident", "P1", "systems_network"),
        ("messaging", "information", "P3", "service_desk"),  # information before messaging
        ("messaging", "incident", "P2", "cloud_collab"),
        ("infrastructure", "service_request", "P3", "systems_network"),
        ("backup", "incident", "P4", "systems_network"),
        ("printing", "incident", "P2", "service_desk"),  # default rule
        ("accounts", "service_request", "P4", "service_desk"),
    ],
)
def test_route_team(taxonomy, category, ticket_type, priority, team):
    assert taxonomy.route_team(category, ticket_type, priority) == team


def test_every_combination_is_routed_to_a_known_team(taxonomy):
    for category in taxonomy.categories:
        for ticket_type in taxonomy.types:
            for priority in taxonomy.priorities:
                assert taxonomy.route_team(category, ticket_type, priority) in taxonomy.teams


def test_route_team_reads_rules_from_the_yaml(tmp_path):
    """Changing the routing in the file changes the result: nothing is hard-coded."""
    with open("config/taxonomy.yaml", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    raw["routing"] = [{"category": ["network"], "team": "security"}, {"team": "service_desk"}]
    path = tmp_path / "taxonomy.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    other = load_taxonomy(path)
    assert other.route_team("network", "incident", "P3") == "security"
    assert other.route_team("accounts", "incident", "P3") == "service_desk"


def test_route_team_without_matching_rule_raises(tmp_path):
    with open("config/taxonomy.yaml", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    raw["routing"] = [{"category": ["network"], "team": "security"}]
    path = tmp_path / "taxonomy.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="No routing rule"):
        load_taxonomy(path).route_team("accounts", "incident", "P3")


def test_invalid_taxonomy_is_rejected(tmp_path):
    with open("config/taxonomy.yaml", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    raw["routing"] = [{"category": ["nope"], "team": "security"}]
    path = tmp_path / "taxonomy.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid taxonomy"):
        load_taxonomy(path)


@pytest.mark.parametrize(
    ("tool", "severity", "priority"),
    [("zabbix", "Disaster", "P1"), ("zabbix", "Warning", "P4"), ("centreon", "DOWN", "P1")],
)
def test_monitoring_priority(taxonomy, tool, severity, priority):
    assert taxonomy.monitoring_priority(tool, severity) == priority


@pytest.mark.parametrize(
    ("check", "category"),
    [
        ("Free disk space is less than 10% on volume C:", "infrastructure"),
        ("VPN tunnel is down", "network"),
        ("Backup job failed", "backup"),
        ("Antivirus definitions are out of date", "security"),
        ("Toner level is low", "printing"),
        ("Mail queue length is too high", None),
    ],
)
def test_category_from_check(taxonomy, check, category):
    assert taxonomy.category_from_check(check) == category

"""Tests of the label-mapping proposal for public datasets."""

from __future__ import annotations

import re

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
        ("Computer-Services", "workstation", True),
        ("Fileservice", "infrastructure", False),  # without text: the default of the class
        ("EOL", "infrastructure", False),
        ("Support general", None, False),  # without text: still vague, excluded
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


# ---------------------------------------------- tasksource: classes cut by keyword rules


def it_support(mapping, label, text):
    return mapping.propose("it_support", {"label": label}, body=text)


@pytest.mark.parametrize(
    "text",
    [
        "File Share Access - [TICKET ID] - [NAME] ([COMPANY]. [LOCATION])",
        "Service Request: File Share Access Grant access to file share for the following user",
        "Remove File Share Access - [TICKET ID] - [NAME] ([COMPANY]. [LOCATION])",
    ],
)
def test_fileservice_share_access_is_an_accounts_service_request(mapping, text):
    proposal = it_support(mapping, "Fileservice", text)
    assert (proposal.category, proposal.type) == ("accounts", "service_request")
    assert proposal.rule == "Fileservice:fileshare_access"
    assert not proposal.doubtful


@pytest.mark.parametrize(
    "text",
    [
        "Please give me permission on the J drive to delete files",
        "Access to R drive for team member",
        "Liberação de acesso pasta J: Marketing",
        "Ordner Zugriffsrechte beschränken",
        "Could you grant my colleague access to the project folder",
    ],
)
def test_fileservice_free_text_access_requests_are_accounts_but_doubtful(mapping, text):
    proposal = it_support(mapping, "Fileservice", text)
    assert proposal.category == "accounts"
    assert proposal.rule == "Fileservice:fileshare_access_free_text"
    assert proposal.doubtful


@pytest.mark.parametrize("text", ["missing folders on J drive", "R Drive cannot rename a folder"])
def test_other_fileservice_tickets_are_infrastructure(mapping, text):
    proposal = it_support(mapping, "Fileservice", text)
    assert proposal.category == "infrastructure"
    assert proposal.rule == "Fileservice:fileservice_other"


def test_eol_server_is_an_infrastructure_service_request_with_priority_p4(mapping):
    proposal = it_support(
        mapping, "EOL", "The following system must be set to End Of Life in Nexthink: [SERVER]"
    )
    assert (proposal.category, proposal.type, proposal.priority) == (
        "infrastructure",
        "service_request",
        "P4",
    )
    assert proposal.rule == "EOL:eol_server"


def test_eol_workstation_follows_the_resource(mapping):
    proposal = it_support(
        mapping, "EOL", "The following laptop must be set to End Of Life in Nexthink"
    )
    assert (proposal.category, proposal.type, proposal.priority) == (
        "workstation",
        "service_request",
        "P4",
    )


@pytest.mark.parametrize(
    "text",
    [
        "Basis User - [USERNAME] - [NAME] ([COMPANY]. [LOCATION])",
        "Light User for external - [TICKET ID] - [NAME]",
        "Service Request: Basis User Create Windows account for internal user",
        "Leaving Employee - [TICKET ID] - [NAME] ([COMPANY]. [LOCATION])",
    ],
)
def test_support_general_account_lifecycle_is_accounts(mapping, text):
    proposal = it_support(mapping, "Support general", text)
    assert (proposal.category, proposal.type) == ("accounts", "service_request")
    assert proposal.rule == "Support general:account_lifecycle"


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Setup BB on mobile phone.", "telephony"),
        ("reconfiguración de mi teléfono corporativo.", "telephony"),
        ("Contacts are gone on iPhone 5", "telephony"),
        ("desconexion del VPN", "network"),
        ("Check DNS/DHCP entries for network 10.10.89.0", "network"),
        ("Kann sich im Intranet nicht anmelden", "accounts"),
        ("[SERVER] OS Updates", "infrastructure"),
        ("equipo no inicia", "workstation"),
        ("New devices installed cant install apps", "software"),
        ("Initiated by [COMPANY] - Vulnerable Office on [SERVER]", "security"),
    ],
)
def test_support_general_obvious_cases_get_a_category(mapping, text, category):
    proposal = it_support(mapping, "Support general", text)
    assert proposal.category == category
    assert proposal.exclusion is None


def test_support_general_vague_tickets_are_excluded_with_a_reason(mapping):
    proposal = it_support(mapping, "Support general", "Alteração de Aprovação")
    assert proposal.category is None
    assert proposal.exclusion == "support_general_unclear"
    assert proposal.rule == "Support general:still_vague"


def test_masking_tags_do_not_trigger_keyword_rules(mapping):
    """The tag "[SERVER]" must not make a vague ticket look like server work."""
    proposal = it_support(mapping, "Support general", "activacion [LOCATION] equipo [SERVER]")
    assert proposal.category is None


def test_first_matching_rule_wins_in_label_rules(mapping):
    # an onboarding template that also mentions a phone stays an accounts ticket
    proposal = it_support(mapping, "Support general", "Basis User - new phone for the user")
    assert proposal.category == "accounts"


def test_label_rules_are_data_not_code(tmp_path):
    custom = {
        "it_support": {
            "label_rules": {
                "EOL": {
                    "rules": [{"name": "r", "category": "backup", "patterns": ["tape"]}],
                    "default": {"name": "d", "category": "infrastructure"},
                }
            }
        }
    }
    path = tmp_path / "mapping.yaml"
    path.write_text(yaml.safe_dump(custom), encoding="utf-8")
    loaded = load_mapping(path)
    tape = loaded.propose("it_support", {"label": "EOL"}, body="old tape drive")
    box = loaded.propose("it_support", {"label": "EOL"}, body="old box")
    assert (tape.category, box.category) == ("backup", "infrastructure")


def test_load_mapping_rejects_unknown_category_and_bad_regex_in_label_rules(tmp_path):
    bad_category = {
        "it_support": {
            "label_rules": {"EOL": {"rules": [], "default": {"name": "d", "category": "nope"}}}
        }
    }
    path = tmp_path / "bad_category.yaml"
    path.write_text(yaml.safe_dump(bad_category), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown category"):
        load_mapping(path)

    bad_regex = {
        "it_support": {
            "label_rules": {
                "EOL": {
                    "rules": [{"name": "r", "category": "backup", "patterns": ["(unclosed"]}],
                    "default": {"name": "d", "exclude": "x"},
                }
            }
        }
    }
    path = tmp_path / "bad_regex.yaml"
    path.write_text(yaml.safe_dump(bad_regex), encoding="utf-8")
    with pytest.raises(re.error):
        load_mapping(path)

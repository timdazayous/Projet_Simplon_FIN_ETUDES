"""Tests of the tag convention (Issue #54): invented texts only, no real data."""

from __future__ import annotations

import pytest

from src.data.fictive import FIRST_NAMES, LAST_NAMES
from src.data.tags import CONVENTION_TAGS, apply_convention, count_tags, leftover_tags


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("appelez <tel_num>", "appelez [PHONE]"),
        ("compte <acc_num>", "compte [ACCOUNT_NUMBER]"),
        ("Bonjour <name>,", "Bonjour [NAME],"),
        ("Bonjour <nom>,", "Bonjour [NAME],"),
        ("écrire à <email>", "écrire à [EMAIL]"),
        ("Cordialement, [Votre nom]", "Cordialement, [NAME]"),
        ("Cordialement, [nom]", "Cordialement, [NAME]"),
        ("Cordialement, [Nom]", "Cordialement, [NAME]"),
        ("chez [Your Company]", "chez [COMPANY]"),
        ("voir [Image]", "voir [IMAGE]"),
        ("voir [Crédit photographique]", "voir [IMAGE]"),
        ("ligne un<br>ligne deux<br/>trois", "ligne un\nligne deux\ntrois"),
        ("hôte <IP>", "hôte [IP]"),
        ("écrire à jean.dupont@exemple.fr", "écrire à [EMAIL]"),
    ],
)
def test_old_spellings_become_the_convention(old, new):
    result = apply_convention(old)
    assert result == new
    assert not leftover_tags(result)


def test_convention_tags_are_left_alone():
    text = "[NAME] de [COMPANY] à [LOCATION], serveur [SERVER], [TICKET ID], [URGENT] panne"
    assert apply_convention(text) == text
    assert not leftover_tags(text)


def test_real_text_is_not_rewritten_beyond_the_tags():
    # A first name in a real text is already masked by the source: it must not be touched.
    assert apply_convention("Merci Camille, le Pierre-Hugo ne marche pas") == (
        "Merci Camille, le Pierre-Hugo ne marche pas"
    )


def test_generated_fictitious_data_become_tags():
    first, last = FIRST_NAMES[0], LAST_NAMES[0]
    text = (
        f"RE: [Ticket #20439] Panne\nBonjour,\nVoir #20439 sur CLA-SRV-AD01 ({first} {last}), "
        f"{first} a le mot de passe FAKE-PWD-abc123xyz0. Appelez le 01 99 00 52 02 ou "
        "écrivez à camille.vaudrelle@mortelaine.test, IP 192.0.2.17. Cabinet Mortelaine."
    )
    result = apply_convention(text, fictitious=True)
    assert result == (
        "RE: [TICKET ID] Panne\nBonjour,\nVoir [TICKET ID] sur [SERVER] ([NAME]), "
        "[NAME] a le mot de passe [PASSWORD]. Appelez le [PHONE] ou "
        "écrivez à [EMAIL], IP [IP]. [COMPANY]."
    )
    assert not leftover_tags(result)


def test_leftover_tags_reports_what_the_convention_does_not_cover():
    text = "<br> <name> [Votre nom] [Ticket #12345] x@y.test FAKE-KEY-abc [URGENT] [NAME]"
    found = leftover_tags(text)
    assert set(found) == {
        "<br>",
        "<name>",
        "[Votre nom]",
        "[Ticket #12345]",
        "x@y.test",
        "FAKE-KEY-abc",
    }


def test_count_tags_counts_only_convention_tags():
    counts = count_tags(["[NAME] et [NAME] [URGENT]", "[SERVER] [autre]"])
    assert counts == {"[NAME]": 2, "[SERVER]": 1}
    assert set(counts) <= CONVENTION_TAGS

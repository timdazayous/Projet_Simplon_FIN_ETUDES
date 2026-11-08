"""Tests of the pseudonymisation and masking module (Issue #53). All data are fictitious."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from src.data.fictive import fictive_secret
from src.data.generator import generate
from src.data.pseudonymize import (
    PseudonymizationKeyError,
    Pseudonymizer,
    load_key,
)

KEY = "k" * 40


@pytest.fixture
def pseudo() -> Pseudonymizer:
    return Pseudonymizer(KEY)


# --------------------------------------------------------------------------- pseudonyms


def test_pseudonym_is_stable_and_has_no_trace_of_the_value(pseudo: Pseudonymizer) -> None:
    first = pseudo.pseudonym("camille.vaudrelle@fournilune.test")
    assert first == pseudo.pseudonym("camille.vaudrelle@fournilune.test")
    assert "camille" not in first and "@" not in first
    assert first.startswith("person-") and len(first) == len("person-") + 16


def test_pseudonym_ignores_case_and_surrounding_spaces(pseudo: Pseudonymizer) -> None:
    assert pseudo.pseudonym(" Anne@X.test ") == pseudo.pseudonym("anne@x.test")


def test_pseudonym_depends_on_the_key_and_on_the_kind(pseudo: Pseudonymizer) -> None:
    other = Pseudonymizer("z" * 40)
    assert pseudo.pseudonym(7) != other.pseudonym(7)  # a different key gives different pseudonyms
    assert pseudo.pseudonym(7, "person") != pseudo.pseudonym(7, "ticket")
    assert pseudo.pseudonym(7) == pseudo.pseudonym("7")


def test_no_collision_among_many_identifiers(pseudo: Pseudonymizer) -> None:
    values = {pseudo.pseudonym(i) for i in range(20000)}
    assert len(values) == 20000


def test_short_key_is_refused_and_never_shown() -> None:
    with pytest.raises(PseudonymizationKeyError) as error:
        Pseudonymizer("court-secret")
    assert "court-secret" not in str(error.value)


def test_repr_hides_the_key(pseudo: Pseudonymizer) -> None:
    assert KEY not in repr(pseudo)


def test_load_key_from_env_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"PSEUDONYMIZATION_KEY={KEY}\n", "utf-8")
    assert load_key(env) == KEY
    env.write_text("PSEUDONYMIZATION_KEY=abc\n", "utf-8")
    with pytest.raises(PseudonymizationKeyError) as error:
        load_key(env)
    assert "abc" not in str(error.value)
    env.write_text("AUTRE=1\n", "utf-8")
    with pytest.raises(PseudonymizationKeyError):
        load_key(env)
    with pytest.raises(PseudonymizationKeyError):
        load_key(tmp_path / "absent")


# --------------------------------------------------------------------------- masking


@pytest.mark.parametrize(
    ("text", "forbidden"),
    [
        ("Écrivez à anne.durand@client-exemple.fr svp", "anne.durand"),
        ("Contact : o'brien+tickets@sous.domaine.example.org", "brien"),
        ("Appelez le 01 99 00 12 34 demain", "01 99 00"),
        ("Mon portable : 06.39.98.12.34", "06.39.98"),
        ("Standard : +33 1 99 00 12 34", "99 00"),
        ("Numéro : 0033199001234", "199001234"),
        ("Mon mot de passe actuel est Zx9-hunter2, merci", "hunter2"),
        ("password: Tr0ub4dor&3", "Tr0ub4dor"),
        ("Voici le code d'accès que j'utilise : 4815-xx", "4815"),
        ("La clé fournie par l'éditeur est ABCD-EFGH-1234", "ABCD-EFGH"),
        ("token=abcdef0123456789", "abcdef0123456789"),
        ("clé API sk-proj-0123456789abcdefghij", "0123456789abcdefghij"),
        ("AWS AKIAIOSFODNN7EXAMPLE utilisée", "AKIAIOSFODNN7EXAMPLE"),
        ("jeton ghp_0123456789abcdefghijABCDEFGHIJ", "ghp_0123456789"),
        ("hash 9e107d9d372bb6826bd81d3542a419d6 en clair", "9e107d9d"),
        (
            "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N",
            "eyJhbGci",
        ),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow\nabc\n-----END RSA PRIVATE KEY-----", "MIIEow"),
    ],
)
def test_sensitive_values_disappear(pseudo: Pseudonymizer, text: str, forbidden: str) -> None:
    result = pseudo.mask_text(text)
    assert forbidden not in result.text
    assert sum(result.counts.values()) >= 1


def test_known_names_are_masked_whatever_the_case_and_the_part(pseudo: Pseudonymizer) -> None:
    text = (
        "Bonjour, ici CAMILLE vaudrelle. Le poste de Camille est lent. Cordialement, C. Vaudrelle"
    )
    result = pseudo.mask_text(text, ["Camille Vaudrelle"])
    assert "amille" not in result.text.lower() and "audrelle" not in result.text.lower()
    assert result.counts["name"] >= 3


def test_a_name_inside_another_word_is_left_alone(pseudo: Pseudonymizer) -> None:
    result = pseudo.mask_text("Le télétravail de Léa et la cléa", ["Léa"])
    assert "cléa" in result.text and "[NAME]" in result.text


def test_ordinary_text_is_left_untouched(pseudo: Pseudonymizer) -> None:
    text = "Ticket #12345 : l'imprimante du 2e étage bloque depuis 14h30, 3 postes (192.0.2.15)."
    assert pseudo.mask_text(text).text == text


def test_masking_is_idempotent(pseudo: Pseudonymizer) -> None:
    once = pseudo.mask_text("mdp: abc123 et a@b.fr au 01 99 00 12 34", ["Léa Roux"]).text
    assert pseudo.mask_text(once).text == once


def test_counts_describe_what_was_masked_without_the_values(pseudo: Pseudonymizer) -> None:
    result = pseudo.mask_text("a@b.fr et c@d.fr, tél 01 99 00 12 34, mot de passe: xyz")
    assert (
        result.counts["email"] == 2 and result.counts["phone"] == 1 and result.counts["secret"] == 1
    )


# --------------------------------------------------------------------------- generated data


def test_no_fictitious_personal_value_or_secret_survives_in_generated_tickets(
    pseudo: Pseudonymizer,
) -> None:
    """The generator lists the fictitious PII it wrote in each ticket: none may remain."""
    tickets, _ = generate(seed=3, n_tickets=400, n_alerts=0)
    with_secret = 0
    for ticket in tickets:
        names = [ticket["requester"]["name"]]
        text = f"{ticket['subject']}\n{ticket['body']}"
        masked = pseudo.mask_text(text, names).text
        for item in ticket["pii"]:
            if item["type"] in ("person", "email", "phone", "secret"):
                assert item["value"] not in masked, item["type"]
        assert "FAKE-" not in masked
        with_secret += ticket["contains_secret"]
    assert with_secret > 0  # the test really exercised secrets


def test_fictive_secrets_are_all_masked(pseudo: Pseudonymizer) -> None:
    rng = random.Random(1)
    for _ in range(50):
        secret = fictive_secret(rng)
        assert secret not in pseudo.mask_text(f"voici {secret} merci").text


def test_every_placeholder_belongs_to_the_corpus_convention(pseudo: Pseudonymizer) -> None:
    """One convention for the whole corpus (src/data/tags.py), or the model learns the source."""
    import re

    from src.data.tags import CONVENTION_TAGS

    text = (
        "Mail a@b.fr, tél 01 99 00 12 34, mot de passe: xyz, Léa Roux, token=abc, "
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"
    )
    masked = pseudo.mask_text(text, ["Léa Roux"]).text
    found = set(re.findall(r"\[[A-Z_ ]+\]", masked))
    assert found == {"[EMAIL]", "[PHONE]", "[PASSWORD]", "[NAME]"}
    assert found <= CONVENTION_TAGS

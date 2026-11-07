"""Tests of the corpus assembly (Issue #46): fictitious tickets only, no real data, no network."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

from src.data.corpus import (
    assemble,
    category_targets,
    group_key,
    join_text,
    leak_check,
    normalise_key,
    public_rows,
    select_public,
    split_external,
    stratified_group_split,
    template_key,
)
from src.data.generator import DEFAULT_CONFIG_PATH, load_config
from src.data.label_mapping import Proposal
from src.data.tags import leftover_tags
from src.data.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parent.parent


class FakeMapping:
    """Reads the proposal from the fake original labels (no real mapping rules involved)."""

    def propose(self, dataset, labels, subject="", body=""):
        return Proposal(
            category=labels.get("cat"),
            type=labels.get("type"),
            priority=labels.get("priority"),
            doubtful=bool(labels.get("doubtful", False)),
            exclusion=labels.get("exclusion"),
        )


def raw_ticket(ident, category, body, *, subject="", **labels):
    return {
        "id": ident,
        "subject": subject,
        "body": body,
        "subject_fr": subject,
        "body_fr": body,
        "original_labels": {"cat": category, **labels},
    }


def distinct_body(index: int) -> str:
    """Texts that differ from the first characters on (so they are not near-duplicates)."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    word = letters[index % 26] + letters[(index // 26) % 26] + letters[(index // 676) % 26]
    return f"{word} {word} {word} problème numéro {word} sur le poste {word} du site {word}"


@pytest.fixture(scope="module")
def taxonomy():
    return load_taxonomy()


@pytest.fixture()
def small_config(tmp_path):
    """The real generator configuration, with a corpus of about 120 messages."""
    cfg = load_config(DEFAULT_CONFIG_PATH)
    cfg["corpus"] = {
        "total": 120,
        "validation_share": 0.25,
        "tuning": {"share": 0.25, "min_test_per_category": 1},
        "test_generated": {"seed": 777, "per_category": {"backup": 5, "procurement": 5}},
    }
    path = tmp_path / "generator.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return path


REFERENCE_IDS = [f"PUB-ITS-{i:05d}" for i in range(5)] + ["PUB-ITS-LIKE"]


def fake_public():
    """200 network tickets (plenty), 4 messaging (rare), 2 telephony, one incomplete."""
    train = [
        raw_ticket(f"PUB-CS-{i:05d}", "network", distinct_body(i), type="incident", priority="P3")
        for i in range(200)
    ]
    train += [
        raw_ticket(f"PUB-CS-M{i}", "messaging", distinct_body(1000 + i), type="information")
        for i in range(4)
    ]
    train += [
        raw_ticket(f"PUB-CS-T{i}", "telephony", distinct_body(2000 + i), priority="P2")
        for i in range(2)
    ]
    # Two near-duplicates of network ticket 0 (same opening, different end).
    base = distinct_body(0)
    train += [
        raw_ticket("PUB-CS-D1", "network", base[:60] + " fin un", type="incident", priority="P3"),
        raw_ticket("PUB-CS-D2", "network", base[:60] + " fin deux", type="incident", priority="P3"),
    ]
    external = [
        raw_ticket(f"PUB-ITS-{i:05d}", "accounts", distinct_body(5000 + i), doubtful=i % 2 == 0)
        for i in range(40)
    ]
    # An external ticket that looks like a training one: the training copy must disappear.
    external.append(raw_ticket("PUB-ITS-LIKE", "network", distinct_body(3)[:60] + " autre fin"))
    return train, external


def run_assemble(small_config, taxonomy):
    train, external = fake_public()
    return assemble(
        train,
        external,
        config_path=small_config,
        taxonomy=taxonomy,
        mapping=FakeMapping(),
        reference_ids=REFERENCE_IDS,
    )


# ----------------------------------------------------------------- keys and rows


def test_keys_ignore_digits_punctuation_case_and_tags():
    assert normalise_key("Bonjour [NAME], le PC n°12 ne démarre pas !") == normalise_key(
        "bonjour le pc n 99 ne démarre pas"
    )
    assert len(template_key("a" * 200)) == 50
    assert normalise_key("a" * 200) == "a" * 200


def test_join_text_keeps_the_text_untouched():
    assert join_text("", "Corps [NAME] et FAKE-TOKEN") == "Corps [NAME] et FAKE-TOKEN"
    assert join_text("Sujet", "Corps") == "Sujet\nCorps"


def test_public_rows_keep_missing_labels_as_none_and_drop_excluded():
    raw = [
        raw_ticket("A", "network", "texte un"),
        raw_ticket("B", "network", "texte deux", type="incident", priority="P2", doubtful=True),
        raw_ticket("C", "network", "texte trois", exclusion="trop vague"),
        raw_ticket("D", None, "texte quatre"),
    ]
    rows, dropped = public_rows(raw, "any", FakeMapping())
    assert [r["id"] for r in rows] == ["A", "B"]
    assert rows[0]["type"] is None and rows[0]["priority"] is None
    assert rows[1]["type"] == "incident" and rows[1]["doubtful"] is True
    assert dropped == {"excluded_by_rule": 1, "no_category": 1}


def test_masking_tags_are_preserved_in_the_text():
    raw = [
        raw_ticket("A", "network", "Bonjour [NAME], serveur [SERVER] FAKE-PWD-xyz", subject="Re")
    ]
    rows, _ = public_rows(raw, "any", FakeMapping())
    assert rows[0]["text"] == "Re\nBonjour [NAME], serveur [SERVER] FAKE-PWD-xyz"


# ----------------------------------------------------------------- volumes


def test_category_targets_sum_to_the_total_and_follow_the_weights():
    weights = {"a": 12, "b": 5, "c": 5}
    targets = category_targets(weights, 6000)
    assert sum(targets.values()) == 6000
    assert targets["a"] == round(6000 * 12 / 22)
    cfg = load_config()
    real = category_targets(cfg["free_text"]["categories"], 6000)
    assert sum(real.values()) == 6000
    assert real["messaging"] == 706 and real["procurement"] == 294


def test_select_public_caps_at_the_target_and_is_reproducible():
    rows = [{"id": f"P{i}", "category": "network", "text": str(i)} for i in range(50)] + [
        {"id": f"Q{i}", "category": "backup", "text": str(i)} for i in range(3)
    ]
    targets = {"network": 10, "backup": 8, "telephony": 4}
    selected, need = select_public(rows, targets, seed=1)
    assert Counter(r["category"] for r in selected) == {"network": 10, "backup": 3}
    assert need == {"network": 0, "backup": 5, "telephony": 4}
    again, _ = select_public(rows, targets, seed=1)
    other, _ = select_public(rows, targets, seed=2)
    assert selected == again
    assert {r["id"] for r in selected} != {r["id"] for r in other}


def test_select_public_rejects_a_category_without_target():
    with pytest.raises(ValueError, match="without target"):
        select_public([{"id": "x", "category": "inconnue", "text": "t"}], {"network": 1}, 1)


# ----------------------------------------------------------------- split


def test_split_is_stratified_and_keeps_near_duplicates_together():
    rows = []
    for category in ("a", "b"):
        for i in range(40):
            rows.append(
                {"id": f"{category}{i}", "source": "public", "category": category,
                 "text": distinct_body(i + (0 if category == "a" else 500))}
            )  # fmt: skip
    # A family of 4 near-duplicates in category a.
    for i in range(4):
        rows.append(
            {"id": f"dup{i}", "source": "public", "category": "a",
             "text": "même début de texte pour tous ces tickets identiques " + "x" * i}
        )  # fmt: skip
    train, validation = stratified_group_split(rows, 0.25, seed=3)
    assert len(train) + len(validation) == len(rows)
    by_cat = Counter(r["category"] for r in validation)
    assert 8 <= by_cat["a"] <= 12 and by_cat["b"] == 10
    validation_ids = {r["id"] for r in validation}
    family_sides = {r["id"] in validation_ids for r in rows if r["id"].startswith("dup")}
    assert len(family_sides) == 1
    assert {r["id"] for r in train}.isdisjoint({r["id"] for r in validation})


def test_split_is_reproducible():
    rows = [
        {"id": f"r{i}", "source": "public", "category": "a", "text": distinct_body(i)}
        for i in range(60)
    ]
    assert stratified_group_split(rows, 0.2, seed=9) == stratified_group_split(rows, 0.2, seed=9)


def test_leak_check_detects_identical_and_near_duplicate_texts():
    one = {"id": "1", "source": "public", "category": "a", "text": "un texte assez long " * 5}
    near = {"id": "2", "source": "public", "category": "a", "text": one["text"] + " en plus"}
    other = {"id": "3", "source": "public", "category": "a", "text": "tout autre sujet " * 5}
    result = leak_check({"x": [one], "y": [near], "z": [other]})
    assert result["x|y"] == {"identical_texts": 0, "near_duplicate_keys": 1}
    assert result["x|z"] == {"identical_texts": 0, "near_duplicate_keys": 0}
    assert leak_check({"x": [one], "y": [dict(one, id="9")]})["x|y"]["identical_texts"] == 1


def test_group_key_of_generated_tickets_is_the_whole_text():
    long_a = {"source": "generated", "text": "même début " * 10 + "a"}
    long_b = {"source": "generated", "text": "même début " * 10 + "b"}
    assert group_key(long_a) != group_key(long_b)
    assert group_key(dict(long_a, source="public")) == group_key(dict(long_b, source="public"))


# ----------------------------------------------------------------- assembly


def test_assembly_volumes_per_category(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    corpus = [*subsets["train"], *subsets["validation"]]
    targets = report["targets"]
    assert sum(targets.values()) == 120
    assert len(corpus) == 120
    counts = Counter(r["category"] for r in corpus)
    for category, target in targets.items():
        # Near-duplicate keys moved to training never change the volume of a category.
        assert counts[category] == target
    public = Counter(r["category"] for r in corpus if r["source"] == "public")
    available = {"network": 200 + 2 - 1, "messaging": 4, "telephony": 2}  # one look-alike removed
    for category, expected in available.items():
        assert public[category] == min(expected, targets[category])
    generated = Counter(r["category"] for r in corpus if r["source"] == "generated")
    assert all(generated[c] == targets[c] - public[c] for c in targets), (
        "the generator provides exactly what the public data lacks"
    )
    assert report["generator_need"] == {c: targets[c] - public[c] for c in targets}


def test_validation_share_is_stratified(small_config, taxonomy):
    subsets, _ = run_assemble(small_config, taxonomy)
    total = Counter(r["category"] for r in (*subsets["train"], *subsets["validation"]))
    valid = Counter(r["category"] for r in subsets["validation"])
    for category in ("network", "accounts", "backup", "security"):
        if total[category] >= 8:
            assert abs(valid[category] / total[category] - 0.25) <= 0.15, category


def test_no_leak_between_subsets(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    for pair in report["leak_check"].values():
        assert pair == {"identical_texts": 0, "near_duplicate_keys": 0}
    names = list(subsets)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            texts_a = {r["text"] for r in subsets[first]}
            assert texts_a.isdisjoint({r["text"] for r in subsets[second]})
    ids = [r["id"] for rows in subsets.values() for r in rows]
    assert len(ids) == len(set(ids))


def test_external_test_never_enters_the_training(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    assert all(
        r["source"] == "public" and r["id"].startswith("PUB-ITS") for r in subsets["test_external"]
    )
    training_ids = {r["id"] for r in (*subsets["train"], *subsets["validation"])}
    assert not any(i.startswith("PUB-ITS") for i in training_ids)
    # The training ticket that looked like an external one was removed from the pool.
    assert report["dropped"]["train_pool_like_external_test"] == 1
    assert len(subsets["test_external"]) + len(subsets["tuning"]) == 41


def test_near_duplicates_stay_on_the_same_side(small_config, taxonomy):
    subsets, _ = run_assemble(small_config, taxonomy)
    keys_train = {group_key(r) for r in subsets["train"]}
    keys_valid = {group_key(r) for r in subsets["validation"]}
    assert keys_train.isdisjoint(keys_valid)


def test_generated_test_covers_only_the_configured_categories(small_config, taxonomy):
    subsets, _ = run_assemble(small_config, taxonomy)
    rows = subsets["test_generated"]
    assert Counter(r["category"] for r in rows) == {"backup": 5, "procurement": 5}
    assert all(r["source"] == "generated" and r["id"].startswith("GEN-X") for r in rows)
    training = {normalise_key(r["text"]) for r in (*subsets["train"], *subsets["validation"])}
    assert not any(normalise_key(r["text"]) in training for r in rows)


def test_missing_labels_are_kept_and_reported(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    external = subsets["test_external"]
    assert all(r["type"] is None and r["priority"] is None for r in external)
    described = report["subsets"]["test_external"]
    rows = len(external)
    assert described["completeness"] == {
        "category": rows,
        "type": 0,
        "priority": 0,
        "doubtful": rows,
    }
    split = (
        described["completeness_doubtful"]["rows"] + described["completeness_not_doubtful"]["rows"]
    )
    assert split == rows
    train = report["subsets"]["train"]
    # Fake telephony tickets have no type: the gap is reported, not filled.
    assert train["completeness"]["type"] < train["rows"]
    assert train["completeness"]["category"] == train["rows"]
    # Generated tickets always carry the three labels.
    generated = [r for r in subsets["train"] if r["source"] == "generated"]
    assert all(r["type"] and r["priority"] and r["doubtful"] is False for r in generated)


def test_rows_have_the_documented_fields(small_config, taxonomy):
    subsets, _ = run_assemble(small_config, taxonomy)
    for rows in subsets.values():
        for row in rows:
            assert set(row) == {"id", "source", "text", "category", "type", "priority", "doubtful"}
            assert row["source"] in ("public", "generated")
            assert row["category"] in taxonomy.categories


def test_assembly_is_reproducible(small_config, taxonomy):
    first = run_assemble(small_config, taxonomy)
    second = run_assemble(small_config, taxonomy)
    assert first == second


def test_report_contains_no_ticket_text(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    dumped = json.dumps(report, ensure_ascii=False)
    sample = [r["text"] for rows in subsets.values() for r in rows[:5]]
    assert not any(text in dumped for text in sample)
    assert report["generated_diversity_train"]["distinct_texts_share"] > 0.9


def test_assembly_fails_when_a_public_category_has_no_target(small_config, taxonomy):
    train, external = fake_public()
    train.append(raw_ticket("PUB-CS-X", "inconnue", distinct_body(9999)))
    with pytest.raises(ValueError, match="without target"):
        assemble(
            train,
            external,
            config_path=small_config,
            taxonomy=taxonomy,
            mapping=FakeMapping(),
            reference_ids=REFERENCE_IDS,
        )


def test_default_config_has_a_corpus_section():
    cfg = load_config(DEFAULT_CONFIG_PATH)
    assert cfg["corpus"]["total"] == 6000
    assert cfg["corpus"]["validation_share"] == 0.15
    assert set(cfg["corpus"]["test_generated"]["per_category"]) == {
        "backup",
        "procurement",
        "admin_billing",
    }
    assert cfg["corpus"]["test_generated"]["seed"] != cfg["seed"]


# ----------------------------------------------------------------- Issue #54: tuning set


def external_rows(per_category: dict[str, int], *, shared_opening: int = 0):
    """Fake real tickets; the first ``shared_opening`` of 'accounts' share an opening."""
    rows, index = [], 0
    for category, count in per_category.items():
        for i in range(count):
            text = distinct_body(9000 + index)
            if category == "accounts" and i < shared_opening:
                text = "même début de texte pour ces tickets quasi identiques " + "x" * i
            rows.append(
                {"id": f"E{index:03d}", "source": "public", "text": text, "category": category,
                 "type": None, "priority": None, "doubtful": False}
            )  # fmt: skip
            index += 1
    return rows


def test_external_split_is_stratified_and_reproducible():
    rows = external_rows({"accounts": 60, "software": 30, "printing": 20})
    test, tuning = split_external(rows, [], tuning_share=0.3, seed=5, min_test=10)
    assert len(test) + len(tuning) == len(rows)
    assert {r["id"] for r in test}.isdisjoint({r["id"] for r in tuning})
    by_category = Counter(r["category"] for r in tuning)
    assert by_category == {"accounts": 18, "software": 9, "printing": 6}
    assert split_external(rows, [], tuning_share=0.3, seed=5, min_test=10) == (test, tuning)
    other = split_external(rows, [], tuning_share=0.3, seed=6, min_test=10)
    assert {r["id"] for r in other[1]} != {r["id"] for r in tuning}


def test_external_split_keeps_near_duplicates_on_the_same_side():
    rows = external_rows({"accounts": 60, "software": 30}, shared_opening=8)
    test, tuning = split_external(rows, [], tuning_share=0.3, seed=1, min_test=1)
    family = {r["id"] for r in rows if r["text"].startswith("même début")}
    assert len(family) == 8
    tuning_ids = {r["id"] for r in tuning}
    assert len({i in tuning_ids for i in family}) == 1
    assert {group_key(r) for r in test}.isdisjoint({group_key(r) for r in tuning})


def test_reviewed_tickets_and_their_near_duplicates_stay_in_the_test():
    rows = external_rows({"accounts": 60, "software": 30}, shared_opening=8)
    reviewed = [r["id"] for r in rows if r["category"] == "software"][:10]
    reviewed.append(next(r["id"] for r in rows if r["text"].startswith("même début")))
    test, tuning = split_external(rows, reviewed, tuning_share=0.5, seed=2, min_test=1)
    assert set(reviewed) <= {r["id"] for r in test}
    assert all(not r["text"].startswith("même début") for r in tuning)


def test_external_split_stops_when_a_category_has_fewer_than_ten_test_tickets():
    rows = external_rows({"accounts": 60, "security": 12})
    with pytest.raises(ValueError, match=r"fewer than 10 test tickets.*security"):
        split_external(rows, [], tuning_share=0.5, seed=1, min_test=10)
    test, _ = split_external(rows, [], tuning_share=0.5, seed=1, min_test=5)
    assert Counter(r["category"] for r in test)["security"] == 6


def test_external_split_rejects_an_unknown_reviewed_ticket():
    with pytest.raises(ValueError, match="missing"):
        split_external(
            external_rows({"accounts": 10}), ["INCONNU"], tuning_share=0.3, seed=1, min_test=1
        )


def test_assembly_stops_below_the_minimum_of_test_tickets(small_config, taxonomy):
    cfg = yaml.safe_load(small_config.read_text(encoding="utf-8"))
    cfg["corpus"]["tuning"]["min_test_per_category"] = 10
    small_config.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="fewer than 10 test tickets"):
        run_assemble(small_config, taxonomy)


def test_tuning_set_is_distinct_from_every_other_set(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    tuning = subsets["tuning"]
    assert tuning and all(r["id"].startswith("PUB-ITS") for r in tuning)
    assert set(REFERENCE_IDS) <= {r["id"] for r in subsets["test_external"]}
    for other in ("train", "validation", "test_external", "test_generated"):
        leaks = report["leak_check"]
        pair = leaks.get(f"{other}|tuning") or leaks[f"tuning|{other}"]
        assert pair == {"identical_texts": 0, "near_duplicate_keys": 0}, other
    split = report["external_split"]["by_category"]
    assert {c: v["tuning"] + v["test"] for c, v in split.items()} == {"accounts": 40, "network": 1}


def test_leak_check_flags_a_tuning_ticket_copied_into_the_test():
    row = {"id": "1", "source": "public", "category": "a", "text": "un texte unique " * 6}
    leaks = leak_check({"tuning": [row], "test_external": [dict(row, id="2")], "train": []})
    assert leaks["tuning|test_external"]["identical_texts"] == 1


def test_every_source_follows_the_tag_convention(small_config, taxonomy):
    subsets, report = run_assemble(small_config, taxonomy)
    for name, rows in subsets.items():
        assert not any(leftover_tags(r["text"]) for r in rows), name
        assert report["tag_convention"][name]["rows_with_leftover_tags"] == 0
    generated = [r["text"] for r in subsets["train"] if r["source"] == "generated"]
    assert any("[NAME]" in t for t in generated)
    assert not any("@" in t or "FAKE-" in t or "01 99 00" in t for t in generated)

"""Assemble the classification corpus: train, validation and two test sets (Issue #46).

Inputs: the translated public tickets (``*_fr.jsonl`` written by ``scripts/translate_public.py``)
and the synthetic generator. Output: JSONL files plus a ``report.json`` made of counts only (no
ticket text), so that the report can be quoted in the documentation.

Method (see ``docs/donnees/corpus.md``):

1. Labels are recomputed from ``config/public_label_mapping.yaml`` (the files carry old ones).
2. Per category, target = ``total * weight / sum(weights)`` (weights of ``config/generator.yaml``),
   ``public = min(available, target)`` (seeded draw), ``generated = target - public``.
3. Train / validation: stratified by category, near-duplicates kept on the same side.
4. The external test (tasksource) never enters the training; any training text that looks like one
   of its tickets is removed from the training side.
5. A second generated test set, from another seed, covers the categories that have no real test
   ticket. It is optimistic: the phrase templates are shared with the training texts.

Texts are never modified: pseudonymisation and secret tags stay exactly as they are.
"""

from __future__ import annotations

import random
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from src.data import templates as tpl
from src.data.generator import generate, load_config
from src.data.label_mapping import LabelMapping
from src.data.taxonomy import Taxonomy

KEY_LENGTH = 50  # a "near-duplicate" shares the first 50 normalised characters
_TAG = re.compile(r"\[[A-Za-z][A-Za-z0-9 _]*\]")
FIELDS = ("category", "type", "priority", "doubtful")
SUBSETS = ("train", "validation", "test_external", "test_generated")
OVERSAMPLING = 4  # test_generated: draw more texts than needed, then drop the ones seen in training


# --------------------------------------------------------------------------- keys


def normalise_key(text: str, length: int | None = None) -> str:
    """Letters-only, lower-case form of a text; pseudonymisation tags are ignored.

    ``length`` keeps only the first characters (near-duplicate key); ``None`` keeps everything
    (identical-text key).
    """
    text = _TAG.sub(" ", text).lower()
    text = re.sub(r"[^a-zà-ÿ ]", " ", text)
    key = " ".join(text.split())
    return key if length is None else key[:length]


def template_key(text: str) -> str:
    """Near-duplicate key used for the public tickets (first 50 normalised characters)."""
    return normalise_key(text, KEY_LENGTH)


def group_key(row: dict[str, Any]) -> str:
    """Key under which rows must stay on the same side of a split.

    Public tickets: first 50 characters (their quasi-duplicates share an opening). Generated
    tickets: the whole normalised text, because their subjects come from a short list of
    templates, so a prefix key would put whole families on one side by construction.
    """
    if row["source"] == "public":
        return template_key(row["text"])
    return normalise_key(row["text"])


def join_text(subject: str, body: str) -> str:
    """Subject and body in one text, as the generator does (no subject: the body alone)."""
    subject, body = (subject or "").strip(), (body or "").strip()
    return f"{subject}\n{body}" if subject else body


# --------------------------------------------------------------------------- rows


def public_rows(
    raw: Iterable[dict[str, Any]], dataset: str, mapping: LabelMapping
) -> tuple[list[dict[str, Any]], Counter]:
    """Corpus rows of a translated public dataset, labels recomputed from the mapping rules.

    Tickets that the rules exclude, or that stay without category, are dropped and counted.
    Missing type or priority stay ``None``: nothing is invented.
    """
    rows: list[dict[str, Any]] = []
    dropped: Counter = Counter()
    for item in raw:
        proposal = mapping.propose(dataset, item["original_labels"], item["subject"], item["body"])
        if proposal.exclusion:
            dropped["excluded_by_rule"] += 1
        elif proposal.category is None:
            dropped["no_category"] += 1
        else:
            rows.append(
                {
                    "id": item["id"],
                    "source": "public",
                    "text": join_text(item.get("subject_fr", ""), item["body_fr"]),
                    "category": proposal.category,
                    "type": proposal.type,
                    "priority": proposal.priority,
                    "doubtful": proposal.doubtful,
                }
            )
    return rows, dropped


def generated_rows(tickets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Corpus rows of generator tickets (labels come from the generator and the taxonomy)."""
    return [
        {
            "id": t["id"],
            "source": "generated",
            "text": f"{t['subject']}\n{t['body']}",
            "category": t["category"],
            "type": t["type"],
            "priority": t["priority"],
            "doubtful": False,
        }
        for t in tickets
    ]


# --------------------------------------------------------------------------- split of the volume


def category_targets(weights: dict[str, float], total: int) -> dict[str, int]:
    """Share of ``total`` per category (largest-remainder rounding, the sum is exactly total)."""
    weight_sum = float(sum(weights.values()))
    exact = {c: total * w / weight_sum for c, w in weights.items()}
    targets = {c: int(value) for c, value in exact.items()}
    missing = total - sum(targets.values())
    by_remainder = sorted(exact, key=lambda c: (-(exact[c] - targets[c]), c))
    for category in by_remainder[:missing]:
        targets[category] += 1
    return targets


def select_public(
    pool: list[dict[str, Any]], targets: dict[str, int], seed: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Per category: ``public = min(available, target)``, reproducible draw.

    Returns the selected rows and the number of texts the generator must still provide.
    """
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pool:
        by_category[row["category"]].append(row)
    unknown = set(by_category) - set(targets)
    if unknown:
        raise ValueError(f"Public tickets with a category without target: {sorted(unknown)}")
    selected: list[dict[str, Any]] = []
    need: dict[str, int] = {}
    for category in sorted(targets):
        available = sorted(by_category.get(category, []), key=lambda r: r["id"])
        taken = min(len(available), targets[category])
        if taken < len(available):
            available = random.Random(f"{seed}:public:{category}").sample(available, taken)
        selected.extend(available)
        need[category] = targets[category] - taken
    return selected, need


def stratified_group_split(
    rows: list[dict[str, Any]], validation_share: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Train / validation split, stratified by category, near-duplicates on the same side."""
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for category in sorted(by_category):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in sorted(by_category[category], key=lambda r: r["id"]):
            groups[group_key(row)].append(row)
        ordered = [groups[key] for key in sorted(groups)]
        random.Random(f"{seed}:split:{category}").shuffle(ordered)
        wanted = round(validation_share * len(by_category[category]))
        taken = 0
        for group in ordered:
            if taken + len(group) <= wanted:
                validation.extend(group)
                taken += len(group)
            else:
                train.extend(group)
    # The same opening can appear in two categories (groups are built per category): such a key
    # goes entirely to the training side, so that no near-duplicate crosses the split.
    shared = {group_key(r) for r in train} & {group_key(r) for r in validation}
    if shared:
        train.extend(r for r in validation if group_key(r) in shared)
        validation = [r for r in validation if group_key(r) not in shared]
    return train, validation


# --------------------------------------------------------------------------- report


def completeness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Number of rows with a value, per field (``doubtful`` is always filled)."""
    return {field: sum(row[field] is not None for row in rows) for field in FIELDS}


def describe(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts only: volume, sources, categories, label completeness, doubtful split."""
    doubtful = [r for r in rows if r["doubtful"]]
    sure = [r for r in rows if not r["doubtful"]]
    return {
        "rows": len(rows),
        "by_source": dict(sorted(Counter(r["source"] for r in rows).items())),
        "by_category": dict(sorted(Counter(r["category"] for r in rows).items())),
        "by_category_and_source": {
            c: dict(sorted(Counter(r["source"] for r in rows if r["category"] == c).items()))
            for c in sorted({r["category"] for r in rows})
        },
        "completeness": completeness(rows),
        "completeness_doubtful": {"rows": len(doubtful), **completeness(doubtful)},
        "completeness_not_doubtful": {"rows": len(sure), **completeness(sure)},
    }


def leak_check(subsets: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, int]]:
    """Number of identical texts and of near-duplicate keys shared by each pair of subsets."""
    names = list(subsets)
    exact = {n: {normalise_key(r["text"]) for r in subsets[n]} for n in names}
    groups = {n: {group_key(r) for r in subsets[n]} for n in names}
    result: dict[str, dict[str, int]] = {}
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            result[f"{first}|{second}"] = {
                "identical_texts": len(exact[first] & exact[second]),
                "near_duplicate_keys": len(groups[first] & groups[second]),
            }
    return result


def generated_diversity(tickets: list[dict[str, Any]]) -> dict[str, Any]:
    """Share of distinct generated texts, as exact text and without the fictitious data.

    The second figure removes what the generator invents for each message (names, addresses,
    numbers, hosts): what remains is the phrase skeleton, the part that repeats.
    """
    if not tickets:
        return {"rows": 0}

    def skeleton(ticket: dict[str, Any]) -> str:
        text = f"{ticket['subject']}\n{ticket['body']}"
        for item in sorted(ticket["pii"], key=lambda e: -len(e["value"])):
            text = text.replace(item["value"], " ")
        for name in (ticket["client_name"], ticket["requester"]["name"]):
            text = text.replace(name, " ")
        text = re.sub(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b", " ", text)  # hosts, references, invoices
        return normalise_key(text)

    def subject_skeleton(ticket: dict[str, Any]) -> str:
        """Subject without prefix, fictitious data or numbers: close to the template used."""
        text = re.sub(r"^(?:RE: \[Ticket [^\]]*\] |TR : )", "", ticket["subject"])
        for prefix in tpl.SUBJECT_PREFIXES_URGENT:
            text = text.removeprefix(prefix)
        for item in ticket["pii"]:
            text = text.replace(item["value"], " ")
        text = re.sub(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b", " ", text)
        return normalise_key(text)

    total = len(tickets)
    exact = len({f"{t['subject']}\n{t['body']}" for t in tickets})
    bare = len({skeleton(t) for t in tickets})
    subjects = {(t["category"], t["type"], subject_skeleton(t)) for t in tickets}
    per_category = Counter(category for category, _, _ in subjects)
    return {
        "rows": total,
        "distinct_texts": exact,
        "distinct_texts_share": round(exact / total, 4),
        "distinct_skeletons": bare,
        "distinct_skeletons_share": round(bare / total, 4),
        "distinct_subjects": len(subjects),
        "distinct_subjects_by_category": dict(sorted(per_category.items())),
    }


# --------------------------------------------------------------------------- assembly


def assemble(
    public_train: list[dict[str, Any]],
    external: list[dict[str, Any]],
    *,
    config_path: str | Path,
    taxonomy: Taxonomy,
    mapping: LabelMapping,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Build the four subsets and the report from the raw translated public tickets."""
    cfg = load_config(config_path)
    corpus_cfg = cfg["corpus"]
    seed = int(cfg["seed"])

    train_pool, dropped_train = public_rows(public_train, "customer_support", mapping)
    test_external, dropped_external = public_rows(external, "it_support", mapping)

    # The external test never enters the training: remove look-alikes from the training pool.
    external_keys = {template_key(r["text"]) for r in test_external}
    kept_pool = [r for r in train_pool if template_key(r["text"]) not in external_keys]
    removed_like_external = len(train_pool) - len(kept_pool)

    targets = category_targets(cfg["free_text"]["categories"], int(corpus_cfg["total"]))
    unknown = set(targets) - set(taxonomy.categories)
    if unknown:
        raise ValueError(f"Unknown category (not in taxonomy.yaml): {sorted(unknown)}")
    public_selected, need = select_public(kept_pool, targets, seed)

    tickets, _ = generate(
        config_path,
        seed=seed,
        n_alerts=0,
        taxonomy=taxonomy,
        category_counts={c: n for c, n in need.items() if n > 0},
    )
    generated = generated_rows(tickets)

    train, validation = stratified_group_split(
        [*public_selected, *generated], float(corpus_cfg["validation_share"]), seed
    )

    # Second generated test: other seed (so other fictitious clients and draws), and no text
    # already seen in the training or validation sets.
    test_cfg = corpus_cfg["test_generated"]
    seen = {normalise_key(r["text"]) for r in (*train, *validation)}
    seen |= {normalise_key(r["text"]) for r in test_external}
    drawn, _ = generate(
        config_path,
        seed=int(test_cfg["seed"]),
        n_alerts=0,
        taxonomy=taxonomy,
        category_counts={c: n * OVERSAMPLING for c, n in test_cfg["per_category"].items()},
        ticket_id_prefix="GEN-X",
    )
    test_generated: list[dict[str, Any]] = []
    per_category: Counter = Counter()
    for row in generated_rows(drawn):
        key = normalise_key(row["text"])
        if (
            key in seen
            or per_category[row["category"]] >= test_cfg["per_category"][row["category"]]
        ):
            continue
        seen.add(key)
        per_category[row["category"]] += 1
        test_generated.append(row)
    short = {
        c: n - per_category[c] for c, n in test_cfg["per_category"].items() if per_category[c] < n
    }
    if short:
        raise ValueError(f"Not enough distinct generated test texts: missing {short}")

    subsets = {
        "train": sorted(train, key=lambda r: r["id"]),
        "validation": sorted(validation, key=lambda r: r["id"]),
        "test_external": sorted(test_external, key=lambda r: r["id"]),
        "test_generated": test_generated,
    }
    leaks = leak_check(subsets)
    if any(v for pair in leaks.values() for v in pair.values()):
        raise ValueError(f"Leak between subsets: {leaks}")

    report = {
        "seed": seed,
        "validation_share": corpus_cfg["validation_share"],
        "total_target": corpus_cfg["total"],
        "targets": targets,
        "public_available": dict(sorted(Counter(r["category"] for r in kept_pool).items())),
        "public_selected": dict(sorted(Counter(r["category"] for r in public_selected).items())),
        "generator_need": need,
        "dropped": {
            "public_train": dict(dropped_train),
            "test_external": dict(dropped_external),
            "train_pool_like_external_test": removed_like_external,
        },
        "generated_diversity_train": generated_diversity(tickets),
        "subsets": {name: describe(rows) for name, rows in subsets.items()},
        "leak_check": leaks,
    }
    return subsets, report

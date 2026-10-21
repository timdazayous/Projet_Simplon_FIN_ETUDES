"""Map the original labels of public datasets onto ``config/taxonomy.yaml``.

The rules live in ``config/public_label_mapping.yaml`` and are a PROPOSAL until the developer
validates them. Nothing here replaces the original labels: the proposal is stored next to them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.data.taxonomy import Taxonomy, load_taxonomy

DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[2] / "config" / "public_label_mapping.yaml"


@dataclass(frozen=True)
class Proposal:
    """Labels proposed for one ticket. ``None`` means "cannot be mapped"."""

    category: str | None = None
    type: str | None = None
    priority: str | None = None
    rule: str | None = None  # name of the rule that decided the category
    doubtful: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "type": self.type,
            "priority": self.priority,
            "rule": self.rule,
            "doubtful": self.doubtful,
        }


@dataclass(frozen=True)
class LabelMapping:
    """Rules read from the mapping file, validated against the taxonomy."""

    rules: dict[str, dict[str, Any]] = field(default_factory=dict)

    def propose(
        self, dataset: str, labels: dict[str, Any], subject: str = "", body: str = ""
    ) -> Proposal:
        """Return the proposed taxonomy labels for a ticket of ``dataset``.

        ``labels`` holds the original labels (``tags``, ``type``, ``priority`` for the
        customer-support dataset, ``label`` for the IT-support dataset).
        """
        spec = self.rules.get(dataset)
        if spec is None:
            return Proposal()
        if "category_rules" in spec:
            return self._from_rules(spec, labels, subject)
        return self._from_label(spec, labels)

    @staticmethod
    def _from_rules(spec: dict[str, Any], labels: dict[str, Any], subject: str) -> Proposal:
        tags = {str(t).strip().lower() for t in labels.get("tags", []) if t}
        lowered_subject = subject.lower()
        category = rule_name = None
        doubtful = False
        for rule in spec["category_rules"]:
            rule_tags = {t.lower() for t in rule.get("tags", [])}
            keywords = [k.lower() for k in rule.get("keywords", [])]
            if tags & rule_tags or any(k in lowered_subject for k in keywords):
                category, rule_name = rule["category"], rule["name"]
                doubtful = bool(rule.get("doubtful", False))
                break
        return Proposal(
            category=category,
            type=spec["type"].get(labels.get("type")),
            priority=spec["priority"].get(labels.get("priority")),
            rule=rule_name,
            doubtful=doubtful,
        )

    @staticmethod
    def _from_label(spec: dict[str, Any], labels: dict[str, Any]) -> Proposal:
        label = labels.get("label")
        category = spec.get("category", {}).get(label)
        return Proposal(
            category=category,
            rule=f"label:{label}" if label in spec.get("category", {}) else None,
            doubtful=label in spec.get("doubtful", []),
        )


def load_mapping(
    path: str | Path = DEFAULT_MAPPING_PATH, taxonomy: Taxonomy | None = None
) -> LabelMapping:
    """Read the mapping file and fail early if it names a label unknown to the taxonomy."""
    taxonomy = taxonomy or load_taxonomy()
    with open(path, encoding="utf-8") as handle:
        rules = yaml.safe_load(handle)

    def check(value: str | None, allowed: dict[str, str], what: str) -> None:
        if value is not None and value not in allowed:
            raise ValueError(f"Invalid label mapping: unknown {what} '{value}'")

    for spec in rules.values():
        for rule in spec.get("category_rules", []):
            check(rule["category"], taxonomy.categories, "category")
        for value in spec.get("category", {}).values():
            check(value, taxonomy.categories, "category")
        for value in spec.get("type", {}).values():
            check(value, taxonomy.types, "type")
        for value in spec.get("priority", {}).values():
            check(value, taxonomy.priorities, "priority")
    return LabelMapping(rules=rules)

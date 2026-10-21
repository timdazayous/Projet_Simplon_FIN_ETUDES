"""Load ``config/taxonomy.yaml``, the single reference for labels and rules.

Nothing in the project should hard-code a label list: everything goes through
a :class:`Taxonomy` instance. The team is never predicted, it is computed by
:meth:`Taxonomy.route_team` from the routing rules of the YAML file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "config" / "taxonomy.yaml"

# Fields a routing rule may test (the other key, "team", is the result).
_ROUTING_CONDITIONS = ("category", "type", "priority")


@dataclass(frozen=True)
class Taxonomy:
    """Immutable view of the taxonomy file."""

    categories: dict[str, str]
    types: dict[str, str]
    priorities: dict[str, str]
    teams: dict[str, str]
    sources: dict[str, str]
    monitoring_sources: tuple[str, ...]
    routing: tuple[dict[str, Any], ...]
    monitoring_severity: dict[str, dict[str, str]]
    monitoring_check_category: dict[str, tuple[str, ...]]

    def route_team(self, category: str, ticket_type: str, priority: str) -> str:
        """Return the team of the first routing rule that matches.

        A missing condition is not checked; several conditions must all hold.
        """
        values = {"category": category, "type": ticket_type, "priority": priority}
        for rule in self.routing:
            if all(values[key] in rule[key] for key in _ROUTING_CONDITIONS if key in rule):
                return rule["team"]
        raise ValueError(f"No routing rule matches {values}")

    def monitoring_priority(self, tool: str, severity: str) -> str:
        """Map a monitoring tool severity (Zabbix, Centreon) to a project priority."""
        return self.monitoring_severity[tool][severity]

    def category_from_check(self, check_name: str) -> str | None:
        """Category of a monitoring check, from keywords found in its name.

        Categories are tried in file order; ``None`` means no rule matches
        (the alert then goes to the model, as a last resort).
        """
        lowered = check_name.lower()
        for category, keywords in self.monitoring_check_category.items():
            if any(keyword in lowered for keyword in keywords):
                return category
        return None

    @property
    def priority_order(self) -> tuple[str, ...]:
        """Priorities from the most urgent to the least urgent (file order)."""
        return tuple(self.priorities)


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"Invalid taxonomy: {message}")


def load_taxonomy(path: str | Path = DEFAULT_TAXONOMY_PATH) -> Taxonomy:
    """Read and validate the taxonomy file."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    taxonomy = Taxonomy(
        categories=dict(raw["categories"]),
        types=dict(raw["types"]),
        priorities=dict(raw["priorities"]),
        teams=dict(raw["teams"]),
        sources=dict(raw["sources"]),
        monitoring_sources=tuple(raw["monitoring_sources"]),
        routing=tuple(raw["routing"]),
        monitoring_severity={t: dict(m) for t, m in raw["monitoring_severity"].items()},
        monitoring_check_category={
            c: tuple(k.lower() for k in kw) for c, kw in raw["monitoring_check_category"].items()
        },
    )

    vocabularies = {
        "category": taxonomy.categories,
        "type": taxonomy.types,
        "priority": taxonomy.priorities,
    }
    for rule in taxonomy.routing:
        _check(rule["team"] in taxonomy.teams, f"unknown team in rule {rule}")
        for key, allowed in rule.items():
            if key == "team":
                continue
            _check(key in vocabularies, f"unknown condition '{key}' in rule {rule}")
            _check(all(v in vocabularies[key] for v in allowed), f"unknown value in rule {rule}")
    _check(
        all(s in taxonomy.sources for s in taxonomy.monitoring_sources),
        "monitoring_sources must be declared in sources",
    )
    for tool, mapping in taxonomy.monitoring_severity.items():
        _check(all(p in taxonomy.priorities for p in mapping.values()), f"bad priority for {tool}")
    _check(
        all(c in taxonomy.categories for c in taxonomy.monitoring_check_category),
        "monitoring_check_category uses an unknown category",
    )
    return taxonomy

"""Extract end-of-support dates from endoflife.date (Issue #41).

Usage:
    uv run python scripts/fetch_eol.py
    uv run python scripts/fetch_eol.py --only ubuntu php

Exit codes: 0 OK, 1 some products missing (404 or errors), 2 invalid configuration or option,
3 nothing extracted (source unreachable). Output: data/raw/eol/products.jsonl and report.json.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.eol import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    EXIT_CONFIG,
    load_config,
    run_extraction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="configuration YAML")
    parser.add_argument("--only", nargs="+", help="products to fetch (default: all)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # accents on Windows consoles
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:  # initialisation
        config = load_config(args.config)
    except (OSError, KeyError, ValueError) as error:
        print(f"Configuration invalide : {error}")
        return EXIT_CONFIG
    unknown = set(args.only or []) - set(config.products)
    if unknown:
        print(f"Produits hors configuration : {sorted(unknown)}")
        return EXIT_CONFIG

    report = run_extraction(config, args.only)
    print(
        f"{report.products_ok}/{report.products_requested} produits, {report.versions} versions, "
        f"{report.requests} requêtes ({report.from_cache} produits depuis le cache), "
        f"{report.retries} nouvelles tentatives, {report.duration_seconds} s"
    )
    if report.not_found:
        print(f"Introuvables (404) : {report.not_found}")
    if report.failed:
        print(f"En échec : {report.failed}")
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

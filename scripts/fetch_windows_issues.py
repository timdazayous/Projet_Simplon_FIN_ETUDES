"""Scrape the known issues of the Windows updates (Issue #45, source 5: scraping).

Usage:
    uv run python scripts/fetch_windows_issues.py --only windows-11-24h2   # one page (trial run)
    uv run python scripts/fetch_windows_issues.py                          # every tracked page

Reads config/windows_issues.yaml, obeys robots.txt, sends one request every 2 seconds at most,
saves data/raw/windows_known_issues/issues.jsonl (ignored by Git: Microsoft Learn terms of use
forbid redistribution) and data/raw/windows_known_issues/report.json. A page unchanged since the
last run (saved ETag) is not downloaded again; an interrupted run resumes where it stopped.

Exit codes: 0 ok, 1 partial (some pages failed), 2 configuration, 3 robots.txt refusal,
4 page structure not recognised, 5 network failure.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx2  # noqa: E402

from src.data.windows_issues import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    EXIT_OK,
    EXIT_PARTIAL,
    ExtractionError,
    load_config,
    run_extraction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="configuration YAML")
    parser.add_argument(
        "--only", nargs="+", metavar="SLUG", help="download only these tracked pages (by slug)"
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # accents on Windows consoles
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        config = load_config(args.config)  # initialisation
        with httpx2.Client(
            headers={"User-Agent": config.user_agent},
            timeout=config.timeout_seconds,
            follow_redirects=True,
        ) as client:
            report = run_extraction(config, client, only=args.only)
    except ExtractionError as error:
        print(f"ARRÊT ({error.status}) : {error}")
        return error.exit_code
    print(
        f"windows_known_issues : {report.issues_seen} problèmes vus "
        f"({report.new} nouveaux, {report.updated} modifiés, {report.unchanged} inchangés), "
        f"{report.pages_downloaded} pages téléchargées, {report.pages_not_modified} inchangées, "
        f"{report.requests} requêtes, {report.duration_seconds} s, échecs {len(report.failures)}"
    )
    return EXIT_PARTIAL if report.failures else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

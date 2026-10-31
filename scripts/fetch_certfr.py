"""Extract the CERT-FR security advisories from its JSON API (Issue #42, source 4).

Usage:
    uv run python scripts/fetch_certfr.py --limit 5 --months 1     # small trial run
    uv run python scripts/fetch_certfr.py                          # last 12 months, incremental

Reads config/certfr.yaml, obeys robots.txt, sends one request every 2 seconds at most, saves
data/raw/certfr/avis.jsonl (ignored by Git) and data/raw/certfr/report.json. Advisories already
saved are not downloaded again (unless revised since).

Exit codes: 0 ok, 1 partial (some advisories failed), 2 configuration, 3 robots.txt refusal,
4 API format changed, 5 network failure.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx2  # noqa: E402

from src.data.certfr import (  # noqa: E402
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
    parser.add_argument("--limit", type=int, help="download at most N new advisories (test run)")
    parser.add_argument("--months", type=int, help="period in months (default: from the config)")
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
            report = run_extraction(config, client, limit=args.limit, months=args.months)
    except ExtractionError as error:
        print(f"ARRÊT ({error.status}) : {error}")
        return error.exit_code
    print(
        f"certfr : {report.avis_written} avis écrits (dont {report.revised} révisés), "
        f"{report.up_to_date} à jour, {report.requests} requêtes, "
        f"{report.duration_seconds} s, échecs {len(report.failures)}"
    )
    return EXIT_PARTIAL if report.failures else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

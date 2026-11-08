"""Extract the GLPI tickets by SQL, pseudonymised on import (Issue #53).

Usage:
    uv run python scripts/extract_glpi_sql.py                 # incremental (since the last run)
    uv run python scripts/extract_glpi_sql.py --full          # everything, file rebuilt
    uv run python scripts/extract_glpi_sql.py --since 2026-11-01T00:00:00+00:00 --limit 50
    uv run python scripts/extract_glpi_sql.py --explain       # query plan only, no data read

Secrets (read-only account, pseudonymisation key) come from an env file, ``.env`` by default.
Exit codes: 0 OK, 2 invalid option or configuration, 3 access denied, 4 database unreachable,
5 query failed. Output: data/raw/glpi/tickets.jsonl, state.json, extraction_report.json.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.glpi_sql import (  # noqa: E402
    EXIT_CONFIG,
    SqlConfigError,
    load_sql_config,
    run_extraction,
)
from src.data.pseudonymize import PseudonymizationKeyError, Pseudonymizer, load_key  # noqa: E402


def parse_since(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env", help="file holding the secrets")
    parser.add_argument("--since", type=parse_since, help="ISO 8601 date (UTC if no offset)")
    parser.add_argument("--full", action="store_true", help="ignore the state, rebuild the file")
    parser.add_argument("--limit", type=int, help="maximum number of tickets read")
    parser.add_argument("--explain", action="store_true", help="write the EXPLAIN plan and stop")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.limit is not None and args.limit < 1:
        print("--limit doit être positif")
        return EXIT_CONFIG
    if args.full and args.since:
        print("--full et --since s'excluent")
        return EXIT_CONFIG
    try:  # initialisation
        config = load_sql_config(args.env_file)
        pseudonymizer = Pseudonymizer(load_key(args.env_file))
    except (SqlConfigError, PseudonymizationKeyError) as error:
        print(f"Configuration invalide : {error}")
        return EXIT_CONFIG

    report = run_extraction(
        config,
        pseudonymizer,
        since=args.since,
        full=args.full,
        limit=args.limit,
        explain=args.explain,
    )
    if args.explain:
        print("Plan écrit dans data/raw/glpi/explain.txt" if not report.exit_code() else "Échec")
        return report.exit_code()
    print(
        f"depuis {report.since} : {report.rows_read} tickets lus, {report.records_written} écrits "
        f"(total {report.records_total}), {report.skipped_empty_text} sans texte, "
        f"{report.unknown_category} catégories inconnues, {report.no_category} sans catégorie ; "
        f"masquages : {report.masked} ; {report.retries} reprises, {report.duration_seconds} s"
    )
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

"""Inject generated tickets into GLPI through its API v2 (Issue #52).

Usage:
    uv run python scripts/inject_glpi.py --dry-run
    uv run python scripts/inject_glpi.py --count 5
    uv run python scripts/inject_glpi.py --count 300

Secrets (OAuth client, API user) are read from an env file, ``.env`` by default.
Exit codes: 0 OK, 1 some tickets failed, 2 invalid option or configuration, 3 token refused,
4 GLPI unreachable, 5 missing right (403), 6 entity created without name.
Report: data/raw/glpi/injection_report.json.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.glpi_api import (  # noqa: E402
    GlpiAuthError,
    GlpiClient,
    GlpiConfigError,
    load_api_config,
)
from src.data.glpi_inject import EXIT_AUTH, EXIT_CONFIG, run_injection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env", help="file holding the GLPI_* variables")
    parser.add_argument("--seed", type=int, default=42, help="generator seed (default 42)")
    parser.add_argument("--pool", type=int, default=300, help="size of the generated series")
    parser.add_argument("--count", type=int, default=None, help="tickets to inject (default: pool)")
    parser.add_argument("--dry-run", action="store_true", help="read GLPI, create nothing")
    parser.add_argument(
        "--no-entities",
        action="store_true",
        help="do not create client entities: every ticket goes to the root entity",
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # one line per request is noise

    count = args.pool if args.count is None else args.count
    if not 1 <= count <= args.pool:
        print("--count doit être compris entre 1 et --pool")
        return EXIT_CONFIG
    try:  # initialisation
        config = load_api_config(args.env_file)
    except GlpiConfigError as error:
        print(f"Configuration invalide : {error}")
        return EXIT_CONFIG

    with GlpiClient(config) as client:
        try:
            report = run_injection(
                client,
                seed=args.seed,
                pool=args.pool,
                count=count,
                dry_run=args.dry_run,
                use_entities=not args.no_entities,
            )
        except GlpiAuthError as error:
            print(f"Authentification refusée : {error}")
            return EXIT_AUTH
    mode = "simulation" if report.dry_run else "réel"
    print(
        f"[{mode}] tickets : {report.tickets_created} à créer ou créés, "
        f"{report.tickets_already_present} déjà présents, {report.tickets_failed} en échec ; "
        f"catégories : {report.categories_created} créées, "
        f"{report.categories_existing} existantes ; "
        f"entités : {report.entities_created} créées, {report.entities_existing} existantes ; "
        f"{report.requests} requêtes, {report.token_requests} jetons, {report.retries} reprises, "
        f"{report.duration_seconds} s"
    )
    if report.failure_reasons:
        print(f"Motifs d'échec : {report.failure_reasons}")
    return report.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())

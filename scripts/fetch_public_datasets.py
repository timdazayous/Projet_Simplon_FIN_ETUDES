"""Download, check, clean and sample the public ticket datasets (Issue #29, phase 1).

Usage (needs the uv group "data"):
    uv run --group data python scripts/fetch_public_datasets.py
    uv run --group data python scripts/fetch_public_datasets.py --only it_support --limit 50

Steps: read config/public_datasets.yaml, check each licence on the Hugging Face card (refusal
if it differs), download, clean, sample with the fixed seed, save JSONL in data/raw/public/
(ignored by Git). Translation is a separate step: scripts/translate_public.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.label_mapping import load_mapping  # noqa: E402
from src.data.public_datasets import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    HuggingFaceHub,
    LicenseError,
    load_config,
    run_fetch,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="configuration YAML")
    parser.add_argument("--only", nargs="+", help="dataset names to process (default: all)")
    parser.add_argument("--limit", type=int, help="keep at most N tickets per dataset (test run)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # accents on Windows consoles

    config = load_config(args.config)  # initialisation
    unknown = set(args.only or []) - set(config.datasets)
    if unknown:
        print(f"Jeux inconnus : {sorted(unknown)}. Disponibles : {sorted(config.datasets)}")
        return 2
    mapping = load_mapping()
    try:
        reports = run_fetch(config, mapping, HuggingFaceHub(), args.only, args.limit)
    except LicenseError as error:
        print(f"REFUS : {error}")
        return 3
    failed = [name for name, report in reports.items() if "error" in report]
    for name, report in reports.items():
        if "error" not in report:
            print(
                f"{name}: lus {report['rows_read']}, rejetés {report['rejected']}, "
                f"corrigés {report['corrections']}, gardés {report['kept_after_sampling']}, "
                f"langues {report['languages']}"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

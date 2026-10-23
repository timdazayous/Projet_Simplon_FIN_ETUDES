"""Translate the prepared public tickets to French with OPUS-MT, on CPU (Issue #29).

Usage (needs the uv group "translate"):
    uv run --group translate python scripts/translate_public.py --dataset it_support --limit 50
    uv run --group translate python scripts/translate_public.py --dataset customer_support \
        --threads 4 --beams 4 --resume

One translation process at a time. The run stops cleanly if the available RAM falls under
--min-ram-mb (default 1500). Resource use is sampled every 2 s and saved with the timings in
<output directory>/<dataset>_translation_report.json (ignored by Git). The technical terms of
config/translation_glossary.yaml are protected during translation (--no-glossary to compare).
To translate every dataset in one command, use scripts/translate_all.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.public_datasets import DEFAULT_CONFIG_PATH, load_config  # noqa: E402
from src.data.translation import (  # noqa: E402
    DEFAULT_GLOSSARY_PATH,
    DEFAULT_MIN_AVAILABLE_MB,
    LowMemoryError,
    load_glossary,
    translate_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--glossary", default=str(DEFAULT_GLOSSARY_PATH), help="glossary YAML")
    parser.add_argument("--no-glossary", action="store_true", help="translate without glossary")
    parser.add_argument("--dataset", required=True, help="dataset name (see the configuration)")
    parser.add_argument("--limit", type=int, help="translate only N tickets, mixed languages")
    parser.add_argument("--threads", type=int, default=4, help="torch CPU threads (default 4)")
    parser.add_argument("--batch-size", type=int, default=8, help="segments per batch")
    parser.add_argument("--beams", type=int, default=2, help="beam search width (4 = slower)")
    parser.add_argument("--min-ram-mb", type=float, default=DEFAULT_MIN_AVAILABLE_MB)
    parser.add_argument("--resume", action="store_true", help="skip tickets already translated")
    parser.add_argument("--suffix", default="", help="suffix of the output file names")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    config = load_config(args.config)
    if args.dataset not in config.datasets:
        print(f"Jeu inconnu : {args.dataset}. Disponibles : {sorted(config.datasets)}")
        return 2
    source = config.output_directory / f"{args.dataset}_prepared.jsonl"
    if not source.exists():
        print(f"{source} introuvable : lancer d'abord scripts/fetch_public_datasets.py")
        return 2

    try:
        stats = translate_file(
            source,
            config.output_directory / f"{args.dataset}{args.suffix}_fr.jsonl",
            config.output_directory / f"{args.dataset}{args.suffix}_translation_report.json",
            config.translation_models,
            None if args.no_glossary else load_glossary(args.glossary),
            seed=config.seed,
            limit=args.limit,
            resume=args.resume,
            threads=args.threads,
            batch_size=args.batch_size,
            beams=args.beams,
            min_ram_mb=args.min_ram_mb,
        )
    except LowMemoryError as error:
        print(f"ARRÊT : {error}")
        return 4
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0 if stats["status"] == "ok" else 4


if __name__ == "__main__":
    raise SystemExit(main())

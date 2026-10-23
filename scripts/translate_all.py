"""One command for the full retrieval and translation of the public datasets (Issue #29).

Usage (needs the uv group "translate"; to run at night, one heavy process only):
    uv run --group translate python scripts/translate_all.py

What it does, in one process and in this order:
    1. download (licence checked first), clean, label and sample the three datasets, unless the
       prepared files already exist (--refresh forces it);
    2. translate each dataset to French: beam search 4, 4 threads, batches of 8, technical-term
       glossary, RAM safety net (stops cleanly under 1 500 MB of available memory);
    3. resume by itself: tickets already translated are skipped, so after a stop (RAM guard,
       sleep, power cut) the same command continues where it stopped (--no-resume starts over).

Exit code 0 = everything translated, 3 = licence refused, 4 = stopped by the RAM guard (run the
same command again once memory is free), 1 = a download failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
from src.data.translation import (  # noqa: E402
    DEFAULT_GLOSSARY_PATH,
    DEFAULT_MIN_AVAILABLE_MB,
    LowMemoryError,
    load_glossary,
    translate_file,
)

# Training corpus first, so that a stop loses the least.
ORDER = ["customer_support", "it_support", "support_urgency"]


def stamp(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--glossary", default=str(DEFAULT_GLOSSARY_PATH))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--beams", type=int, default=4)
    parser.add_argument("--min-ram-mb", type=float, default=DEFAULT_MIN_AVAILABLE_MB)
    parser.add_argument("--refresh", action="store_true", help="prepare the datasets again")
    parser.add_argument("--no-resume", action="store_true", help="translate everything again")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    config = load_config(args.config)
    names = [n for n in ORDER if n in config.datasets]
    missing = [n for n in names if not (config.output_directory / f"{n}_prepared.jsonl").exists()]
    if args.refresh or missing:
        stamp("préparation des jeux (téléchargement, nettoyage, étiquettes)")
        try:
            reports = run_fetch(config, load_mapping(), HuggingFaceHub(), names, log=stamp)
        except LicenseError as error:
            stamp(f"REFUS : {error}")
            return 3
        if any("error" in r for r in reports.values()):
            stamp("ÉCHEC d'un téléchargement : voir les messages ci-dessus")
            return 1

    glossary = load_glossary(args.glossary)
    summary = {}
    for name in names:
        stamp(f"traduction de {name}")
        try:
            stats = translate_file(
                config.output_directory / f"{name}_prepared.jsonl",
                config.output_directory / f"{name}_fr.jsonl",
                config.output_directory / f"{name}_translation_report.json",
                config.translation_models,
                glossary,
                seed=config.seed,
                resume=not args.no_resume,
                threads=args.threads,
                batch_size=args.batch_size,
                beams=args.beams,
                min_ram_mb=args.min_ram_mb,
                log=stamp,
            )
        except LowMemoryError as error:
            stamp(f"ARRÊT : {error}. Relancer la même commande quand la mémoire est libre.")
            return 4
        summary[name] = {
            "status": stats["status"],
            "tickets": stats["total_tickets"],
            "seconds": stats["total_seconds"],
        }
        if stats["status"] != "ok":
            stamp(f"ARRÊT : {stats.get('reason')}. Relancer la même commande pour reprendre.")
            return 4
    stamp("terminé : " + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

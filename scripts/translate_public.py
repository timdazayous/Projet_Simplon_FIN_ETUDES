"""Translate the prepared public tickets to French with OPUS-MT, on CPU (Issue #29).

Usage (needs the uv group "translate"):
    uv run --group translate python scripts/translate_public.py --dataset it_support --limit 50
    uv run --group translate python scripts/translate_public.py --dataset customer_support \
        --threads 4 --resume

One translation process at a time. The run stops cleanly if the available RAM falls under
--min-ram-mb (default 1500). Resource use is sampled every 2 s and saved with the timings in
data/raw/public/<dataset>_translation_report.json (ignored by Git).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.public_datasets import DEFAULT_CONFIG_PATH, load_config  # noqa: E402
from src.data.translation import (  # noqa: E402
    DEFAULT_MIN_AVAILABLE_MB,
    MemoryGuard,
    OpusTranslator,
    ResourceMonitor,
    append_jsonl,
    read_jsonl,
    select_mixed_sample,
    translate_records,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
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
    target = config.output_directory / f"{args.dataset}{args.suffix}_fr.jsonl"
    report_path = config.output_directory / f"{args.dataset}{args.suffix}_translation_report.json"

    records = read_jsonl(source)
    if args.limit:
        records = select_mixed_sample(records, args.limit, config.seed)
    if args.resume and target.exists():
        done = {r["id"] for r in read_jsonl(target)}
        records = [r for r in records if r["id"] not in done]
    elif target.exists():
        target.unlink()  # a fresh run replaces the previous output
    print(f"{len(records)} tickets à traduire, {args.threads} threads, lots de {args.batch_size}")

    guard = MemoryGuard(args.min_ram_mb)
    guard.check("avant le démarrage")
    translator = OpusTranslator(
        config.translation_models, guard, args.threads, args.batch_size, args.beams
    )
    with ResourceMonitor(interval=2.0) as monitor:
        stats = translate_records(
            records,
            translator.translate,
            guard,
            lambda chunk: append_jsonl(target, chunk),
            config.translation_models,
        )
    stats["resources"] = monitor.summary()
    stats["settings"] = {
        "threads": args.threads,
        "batch_size": args.batch_size,
        "beams": args.beams,
        "min_ram_mb": args.min_ram_mb,
    }
    stats["model_revisions"] = translator.revisions
    stats["model_load_seconds"] = translator.load_seconds
    report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0 if stats["status"] == "ok" else 4


if __name__ == "__main__":
    raise SystemExit(main())

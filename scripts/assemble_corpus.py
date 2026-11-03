"""Assemble the classification corpus (train, validation, external and generated tests).

Usage:
    uv run python scripts/assemble_corpus.py
    uv run python scripts/assemble_corpus.py --public-dir DIR --out-dir DIR

Reads ``customer_support_fr.jsonl`` and ``it_support_fr.jsonl`` from the public directory and
writes ``train``, ``validation``, ``test_external``, ``test_generated`` (JSONL) and ``report.json``
(counts only) to the output directory. Both are ignored by Git. Method: docs/donnees/corpus.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data.corpus import SUBSETS, assemble  # noqa: E402
from src.data.generator import DEFAULT_CONFIG_PATH, read_jsonl, write_jsonl  # noqa: E402
from src.data.label_mapping import load_mapping  # noqa: E402
from src.data.taxonomy import load_taxonomy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--public-dir", default=str(ROOT / "data" / "raw" / "public"))
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "processed" / "corpus"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="generator YAML file")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    public_dir, out_dir = Path(args.public_dir), Path(args.out_dir)
    train_raw = read_jsonl(public_dir / "customer_support_fr.jsonl")
    external_raw = read_jsonl(public_dir / "it_support_fr.jsonl")

    subsets, report = assemble(
        train_raw,
        external_raw,
        config_path=args.config,
        taxonomy=load_taxonomy(),
        mapping=load_mapping(),
    )
    for name in SUBSETS:
        count = write_jsonl(out_dir / f"{name}.jsonl", subsets[name])
        print(f"{name}: {count} lignes")
    report_path = out_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Rapport : {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate synthetic tickets and monitoring alerts (JSONL), all data fictitious.

Usage:
    uv run python scripts/generate_synthetic.py
    uv run python scripts/generate_synthetic.py --seed 7 --tickets 100 --alerts 50 --out-dir /tmp/x

Defaults come from config/generator.yaml. Output goes to data/raw/ (ignored by Git).
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.generator import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    generate,
    load_config,
    write_jsonl,
)


def _share(records: list[dict], key: str) -> str:
    counts = Counter(r[key] for r in records)
    total = max(len(records), 1)
    return ", ".join(f"{k} {v / total:.0%}" for k, v in sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="generator YAML file")
    parser.add_argument("--seed", type=int, help="override the seed of the configuration")
    parser.add_argument("--tickets", type=int, help="number of free-text tickets")
    parser.add_argument("--alerts", type=int, help="number of monitoring alerts")
    parser.add_argument("--out-dir", help="output directory (default: from the configuration)")
    parser.add_argument("--tickets-file", help="tickets file name (default: from configuration)")
    parser.add_argument("--alerts-file", help="alerts file name (default: from configuration)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # accents on Windows consoles

    cfg = load_config(args.config)
    out_dir = Path(args.out_dir or cfg["output"]["directory"])
    tickets_path = out_dir / (args.tickets_file or cfg["output"]["tickets_file"])
    alerts_path = out_dir / (args.alerts_file or cfg["output"]["alerts_file"])

    started = time.perf_counter()
    tickets, alerts = generate(
        args.config, seed=args.seed, n_tickets=args.tickets, n_alerts=args.alerts
    )
    write_jsonl(tickets_path, tickets)
    write_jsonl(alerts_path, alerts)
    elapsed = time.perf_counter() - started

    print(f"{len(tickets)} tickets -> {tickets_path} ({tickets_path.stat().st_size / 1024:.0f} Ko)")
    print(f"{len(alerts)} alertes -> {alerts_path} ({alerts_path.stat().st_size / 1024:.0f} Ko)")
    print(f"Durée : {elapsed:.1f} s")
    for key in ("source", "type", "priority", "category", "team"):
        print(f"  tickets {key}: {_share(tickets, key)}")
    print(f"  alertes priority: {_share(alerts, 'priority')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

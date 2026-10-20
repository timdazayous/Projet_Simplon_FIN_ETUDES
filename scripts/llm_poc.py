"""Measure LLM latency per provider with N calls on FICTIONAL ticket texts.

Usage: uv run python scripts/llm_poc.py 20 [--provider groq|ollama]

Needs a .env (see .env.example). Only fictional texts are sent: never real data.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm import LLMClient, LLMError, load_config  # noqa: E402

# Entirely invented tickets (no real client, person or system).
FICTIONAL_TICKETS = [
    "L'imprimante du service comptabilité de la société Exemple SARL n'imprime plus.",
    "Alerte : espace disque à 95 % sur le serveur de fichiers FICTIF-SRV01.",
    "Un utilisateur fictif n'arrive plus à se connecter à sa messagerie depuis ce matin.",
    "Le VPN de la société Demo SAS se déconnecte toutes les dix minutes.",
    "Demande de création d'un compte pour un nouvel arrivant (nom fictif).",
    "La sauvegarde nocturne du serveur FICTIF-SRV02 a échoué deux nuits de suite.",
]
PROMPT = "Tu aides un technicien. Propose en trois lignes maximum une piste de résolution pour : "


def p95(values: list[float]) -> float:
    """95th percentile (nearest rank)."""
    ordered = sorted(values)
    return ordered[max(0, round(0.95 * len(ordered)) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int, help="number of calls")
    parser.add_argument("--provider", choices=["groq", "ollama"], help="override LLM_PROVIDER")
    args = parser.parse_args()

    if args.provider:
        # Measure that provider alone (no fallback), so the statistics are not mixed.
        os.environ["LLM_PROVIDER"] = args.provider
        os.environ["LLM_FALLBACK_PROVIDER"] = ""
    client = LLMClient(load_config())

    latencies: dict[str, list[float]] = defaultdict(list)
    failures = 0
    for i in range(args.n):
        try:
            result = client.complete(PROMPT + FICTIONAL_TICKETS[i % len(FICTIONAL_TICKETS)])
        except LLMError:
            failures += 1
            continue
        latencies[f"{result.provider}/{result.model}"].append(result.latency_ms)

    print(f"{args.n} calls, {failures} failure(s)")
    for name, values in latencies.items():
        print(
            f"{name}: n={len(values)} mean={statistics.mean(values):.0f} ms "
            f"p95={p95(values):.0f} ms"
        )


if __name__ == "__main__":
    main()

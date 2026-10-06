# Triage IA des tickets et alertes MSP

Projet de fin de formation **Développeur en intelligence artificielle (Simplon)**.

## Problème

Un MSP (prestataire d'infogérance) reçoit des centaines de tickets et d'alertes par jour dans une file unique. Le tri (catégorie, urgence, équipe, recherche de cas similaires) est manuel, lent et source d'erreurs de routage.

## Solution

Pour chaque ticket entrant, l'application :

1. **classe** le ticket (catégorie, urgence, équipe) avec un modèle entraîné dans le projet ;
2. **suggère une piste de résolution** via un LLM, à partir des tickets résolus et de la documentation ;
3. **apprend des corrections** des techniciens (boucle de feedback, ré-entraînement).

L'outil aide le technicien à décider, il n'agit jamais seul.

> Commanditaire fictif : un MSP d'une trentaine de personnes gérant une soixantaine de PME clientes.

## Structure du dépôt

| Dossier | Contenu |
|---|---|
| `src/api/` | API REST (FastAPI) |
| `src/classifier/` | Classifieur entraîné dans le projet |
| `src/llm/` | Abstraction LLM (Groq / Ollama) |
| `src/data/` | Extraction, nettoyage, pseudonymisation |
| `tests/` | Tests pytest |
| `docs/` | Documentation destinée au jury |
| `data/` | Données locales (non versionnées dans Git) |
| `models/` | Modèles entraînés (non versionnés dans Git) |
| `scripts/` | Scripts utilitaires |

## Démarrage

```bash
cp .env.example .env   # puis renseigner les valeurs
```

Les secrets restent uniquement dans `.env` (ignoré par Git).

## Développement

Prérequis : [uv](https://docs.astral.sh/uv/). Les commandes ci-dessous sont celles exécutées par la CI à chaque push et PR (voir [docs/ci.md](docs/ci.md)).

```bash
uv sync                      # installe Python 3.12 et les dépendances
uv run ruff check            # lint
uv run ruff format --check   # vérifie le formatage
uv run pytest --cov          # tests et couverture
```

## Contraintes

- Zéro budget : outils gratuits ou open source.
- Pas de GPU : entraînement sur CPU, compatible runner GitHub Actions.
- RGPD : données pseudonymisées avant tout traitement et avant tout envoi à un service externe.

## Suivi

Les décisions, bugs et incidents sont consignés dans [JOURNAL.md](JOURNAL.md).

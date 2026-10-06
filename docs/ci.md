# Intégration continue (CI)

## Objectif

À chaque modification du code, une chaîne automatique vérifie que le projet reste propre et que les tests passent. Elle détecte les erreurs avant la fusion d'une Pull Request (PR). Elle est volontairement minimale et grandira avec le projet (tests de données, entraînement, build de conteneurs).

## Outil choisi : GitHub Actions

- **Intégré au dépôt** : le dépôt est déjà sur GitHub, il n'y a rien à héberger ni à connecter.
- **Gratuit** pour un dépôt public, ce qui respecte la contrainte « zéro budget ».
- **Configuration versionnée** : le fichier `.github/workflows/ci.yml` vit dans le dépôt, relu comme du code.

**Alternative écartée** : GitLab CI. Elle obligerait à migrer le dépôt vers GitLab, sans gain pour ce projet.

## Déclencheurs

| Événement | Quand |
|---|---|
| `push` | À chaque envoi de commits sur la branche `main` |
| `pull_request` | À l'ouverture et à chaque mise à jour d'une PR |

## Étapes

Le workflow `ci.yml` exécute un seul job sur une machine Ubuntu :

1. **Checkout** : récupération du code.
2. **Installation de uv** : gestionnaire de dépendances Python du projet (action `astral-sh/setup-uv`, avec cache).
3. **`uv sync`** : installation de Python 3.12 et des dépendances, à partir de `pyproject.toml` et `uv.lock`.
4. **`uv run ruff check`** : analyse statique (erreurs, imports, bugs probables).
5. **`uv run ruff format --check`** : vérifie le formatage sans modifier les fichiers.
6. **`uv run pytest --cov`** : exécute tous les tests et mesure la couverture.

Si une étape échoue, les suivantes ne sont pas exécutées et la CI est rouge.

## Exécuter les mêmes commandes en local

```bash
uv sync
uv run ruff check
uv run ruff format --check
uv run pytest --cov
```

Pour corriger automatiquement le formatage : `uv run ruff format`. Pour corriger les erreurs de lint corrigeables : `uv run ruff check --fix`.

## Lire un échec

1. Sur la PR, cliquer sur **Details** à côté de la vérification `CI` en échec (ou ouvrir l'onglet **Actions**).
2. Repérer l'étape marquée en rouge et la déplier.
3. Lire le message : `ruff check` indique fichier, ligne et règle ; `ruff format --check` liste les fichiers à reformater ; `pytest` affiche le test en échec et l'assertion.
4. Reproduire en local avec la commande correspondante, corriger, puis pousser un nouveau commit : la CI se relance.

## Tester la chaîne

Pour vérifier que la CI détecte bien les problèmes, introduire volontairement une erreur (par exemple un `assert False` dans `tests/test_smoke.py`) dans une branche jetable et constater que la CI passe au rouge.

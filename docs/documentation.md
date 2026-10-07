# Documentation : construction et publication

## Objectif

La documentation destinée au jury est écrite en Markdown dans le dossier `docs/`, transformée en site HTML accessible et publiée automatiquement. Chaque modification fusionnée dans `main` met le site à jour sans intervention manuelle.

## Outils

- **MkDocs** : générateur de site statique qui transforme les fichiers Markdown en pages HTML. **Alternative écartée** : Sphinx, plus lourd à configurer pour un besoin de pages de texte.
- **Thème Material for MkDocs** : thème qui déclare la langue de la page, offre une navigation au clavier et un contraste soigné. Il est en mode maintenance depuis novembre 2025 (corrections critiques et de sécurité), ses auteurs développant son successeur Zensical, qui lit le même fichier `mkdocs.yml`. **Alternative écartée** : Zensical, encore en développement précoce (statut « alpha » sur PyPI) ; une migration reste possible plus tard.
- **uv** : installe les dépendances de la documentation, regroupées dans le groupe `docs` de `pyproject.toml` et verrouillées dans `uv.lock`.

La configuration du site est dans le fichier `mkdocs.yml` à la racine du dépôt.

## Commandes en local

| Commande | Rôle |
|---|---|
| `uv sync --group docs` | Installe les dépendances de la documentation |
| `uv run mkdocs serve` | Lance un serveur local (http://127.0.0.1:8000) qui se recharge à chaque modification |
| `uv run mkdocs build --strict` | Construit le site dans `site/` ; échoue au moindre avertissement (lien cassé, page absente de la navigation mal référencée) |

Le dossier `site/` est généré : il est ignoré par Git.

## Workflow de publication

Le fichier `.github/workflows/docs.yml` définit deux jobs.

| Déclencheur | Ce qui se passe |
|---|---|
| `pull_request` | Job **build** : installation (`uv sync --locked --group docs`) puis `mkdocs build --strict`. Une PR dont la documentation est cassée ne peut pas passer la vérification. |
| `push` sur `main` | Job **build**, puis job **deploy** : le site est envoyé à GitHub Pages avec les actions officielles `actions/upload-pages-artifact` et `actions/deploy-pages`. |

Les permissions sont minimales : lecture du contenu pour le build ; les droits `pages: write` et `id-token: write` ne sont accordés qu'au job de déploiement, rattaché à l'environnement `github-pages`.

Un bloc `concurrency` (groupe `pages`, sans annulation en cours) place les exécutions en file d'attente : deux envois rapprochés sur `main` ne lancent donc jamais deux déploiements Pages en parallèle.

Le site publié est accessible à l'adresse : <https://timdazayous.github.io/Projet_Simplon_FIN_ETUDES/>.

## Règles d'accessibilité suivies

- **Langue déclarée** : `language: fr` dans `mkdocs.yml`, qui renseigne l'attribut `lang` des pages.
- **Titres hiérarchisés** : un seul titre de niveau 1 par page, puis des niveaux 2 et 3 sans en sauter.
- **Liens explicites** : le texte d'un lien décrit sa destination (jamais « cliquez ici »).
- **Textes alternatifs** : toute image ou tout schéma a une description textuelle.
- **Contraste et navigation clavier** : fournis par le thème, à vérifier à chaque changement de thème ou de couleurs.
- **Tableaux** : une ligne d'en-tête, pas de tableau pour la mise en page.

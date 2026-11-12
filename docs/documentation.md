# Documentation : construction et publication

## Objectif

La documentation destinée au jury est écrite en Markdown dans le dossier `docs/`, transformée en site HTML accessible et publiée automatiquement. Chaque modification fusionnée dans `main` met le site à jour sans intervention manuelle.

## Outils

- **Zensical** (version 0.1.1, licence MIT, statut « Beta » sur PyPI) : générateur de site statique qui transforme les fichiers Markdown en pages HTML et lit directement le fichier `mkdocs.yml`. Il remplace MkDocs et Material for MkDocs depuis la migration de l'Issue #35 (novembre 2026), Material arrivant en fin de vie le 5 novembre 2026. La version est épinglée sur une version exacte (`zensical==0.1.1`) dans `pyproject.toml` et `uv.lock`. **Alternatives écartées** : rester sur Material for MkDocs épinglé (plus aucun correctif de sécurité) ; Sphinx, plus lourd à configurer pour un besoin de pages de texte. Détails dans [Générateur de documentation : Material ou Zensical](decisions/documentation-zensical.md).
- **Variante de thème `classic`** (`theme: variant: classic` dans `mkdocs.yml`) : reproduit l'apparence de Material, qui déclare la langue de la page, offre une navigation au clavier et un lien d'évitement. **Alternative écartée** : la variante `modern`, dont le contraste n'a pas été contrôlé.
- **uv** : installe les dépendances de la documentation, regroupées dans le groupe `docs` de `pyproject.toml` et verrouillées dans `uv.lock`.

La configuration du site est dans le fichier `mkdocs.yml` à la racine du dépôt.

## Protection des données des visiteurs

Par défaut, le thème (Material comme Zensical) charge ses polices depuis Google Fonts : chaque visiteur transmet alors son adresse IP à Google, sans en être informé, ce qui pose un problème au regard du RGPD. L'option `font: false` du thème désactive ce chargement : le site utilise les polices déjà installées sur l'appareil du visiteur. Le site publié ne charge ainsi aucune ressource depuis un service tiers, ce que l'on vérifie après chaque build avec `grep -rl "fonts.googleapis" site`, qui ne doit rien trouver. **Alternative écartée** : héberger les polices dans le dépôt, qui ajoute des fichiers à maintenir pour un gain purement esthétique.

## Commandes en local

| Commande | Rôle |
|---|---|
| `uv sync --group docs` | Installe les dépendances de la documentation |
| `uv run zensical serve` | Lance un serveur local (http://127.0.0.1:8000) qui se recharge à chaque modification |
| `uv run zensical build --clean --strict` | Construit le site dans `site/` après avoir vidé le dossier ; échoue au moindre avertissement (lien cassé, page absente de la navigation mal référencée) |

Le dossier `site/` est généré : il est ignoré par Git.

## Workflow de publication

Le fichier `.github/workflows/docs.yml` définit deux jobs.

| Déclencheur | Ce qui se passe |
|---|---|
| `pull_request` | Job **build** : installation (`uv sync --locked --group docs`) puis `zensical build --clean --strict`. Une PR dont la documentation est cassée ne peut pas passer la vérification. |
| `push` sur `main` | Job **build**, puis job **deploy** : le site est envoyé à GitHub Pages avec les actions officielles `actions/upload-pages-artifact` et `actions/deploy-pages`. |

Les permissions sont minimales : lecture du contenu pour le build ; les droits `pages: write` et `id-token: write` ne sont accordés qu'au job de déploiement, rattaché à l'environnement `github-pages`.

Le job de déploiement porte un bloc `concurrency` (groupe `pages`, sans annulation en cours) : deux envois rapprochés sur `main` ne lancent jamais deux déploiements Pages en parallèle. Ce bloc est limité au déploiement pour ne pas mettre en file d'attente, ni risquer d'annuler, les vérifications des Pull Requests.

Le site publié est accessible à l'adresse : <https://timdazayous.github.io/Projet_Simplon_FIN_ETUDES/>.

## Règles d'accessibilité suivies

- **Langue déclarée** : `language: fr` dans `mkdocs.yml`, qui renseigne l'attribut `lang` des pages.
- **Titres hiérarchisés** : un seul titre de niveau 1 par page, puis des niveaux 2 et 3 sans en sauter.
- **Liens explicites** : le texte d'un lien décrit sa destination (jamais « cliquez ici »).
- **Textes alternatifs** : toute image ou tout schéma a une description textuelle.
- **Contraste et navigation clavier** : fournis par le thème, à vérifier à chaque changement de thème ou de couleurs.
- **Tableaux** : une ligne d'en-tête, pas de tableau pour la mise en page.

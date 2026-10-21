# Générateur de documentation : Material for MkDocs ou Zensical

**Statut : essai réalisé le 2026-10-21, décision à prendre par le développeur.** Cette page fournit les éléments de choix ; elle ne change rien au site publié. Suivi : Issue #13.

## Contexte

Le site de documentation est construit avec MkDocs et le thème Material for MkDocs. La note de version 9.7.7 de Material annonce la **fin de vie du projet au 5 novembre 2026**. Après cette date, le site continue de se construire, mais sans correctif de sécurité (la 9.7.7 corrige justement une faille XSS dans les suggestions de recherche). De plus, l'avertissement affiché à chaque build rappelle que MkDocs 2.0 supprimera le système de plugins ; le projet est déjà protégé par la contrainte `mkdocs>=1.6,<2` dans `pyproject.toml`.

Le successeur, Zensical, est développé par la même équipe. La version testée est la **0.0.71** (publiée le 16 octobre 2026), classée « Development Status :: 3 - Alpha » sur PyPI, sous licence MIT.

## Protocole de l'essai

1. Build de référence : `uv run --group docs mkdocs build --strict` (Material 9.7.x, MkDocs 1.6).
2. Copie de `docs/` et de `mkdocs.yml` dans un dossier temporaire hors dépôt.
3. Build Zensical sur cette copie, sans modifier le projet ni ses dépendances : `uvx --python 3.12 zensical build --clean --strict -f mkdocs.yml`.
4. Comparaison des fichiers produits, de la recherche et de quelques points d'accessibilité dans le HTML.

Le `mkdocs.yml` actuel ne déclare aucune extension Markdown ni aucun plugin autre que `search`. Aucune page n'utilise d'admonition, d'onglet ni de note de bas de page : l'essai ne teste donc pas ces fonctions.

## Résultats

| Critère | Material for MkDocs | Zensical 0.0.71 |
|---|---|---|
| Lecture du `mkdocs.yml` actuel | Oui | Oui, sans modification |
| Build en mode strict | Réussi | Réussi, « No issues found » |
| Temps de build (hors installation) | 1,9 s | 0,8 s à 1,4 s |
| Pages HTML produites | 19 | 19 (mêmes pages) |
| Navigation | Complète | Complète |
| Taille du site | 3,45 Mo | 1,53 Mo |
| Recherche | `search/search_index.json` (167 Ko) | `search.json` (165 Ko) |
| Attribut `lang="fr"` | Oui | Oui |
| Hiérarchie des titres (page Taxonomie : un titre 1, six titres 2, deux titres 3) | Oui | Identique |
| Lien d'évitement | Oui, vers le titre de la page | Oui, vers une ancre `#__skip` |
| Repères `main` et `nav` étiquetés | Oui | Oui |
| Tableaux (7 sur la page Taxonomie) | Rendus | Rendus |
| Textes de l'interface en français | Oui (recherche, « Effacer ») | Partiel : l'infobulle des ancres de titres reste en anglais (« Permanent link ») ; le libellé du champ de recherche n'a pas été retrouvé dans le HTML de la page d'accueil et n'est pas vérifié |
| Thème par défaut | Material | Variante `modern` (nouvelle apparence) ; la variante `classic` reproduit l'apparence de Material |
| Polices | Roboto via Google Fonts | Inter via Google Fonts |

Ce qui n'a **pas** été vérifié : le contraste des couleurs de la variante `modern`, le rendu visuel dans un navigateur, le fonctionnement réel de la recherche en français (seuls les fichiers d'index ont été comparés), la navigation au clavier.

Constat annexe : dans les deux cas, la feuille de style des polices est chargée depuis Google Fonts, ce qui transmet l'adresse IP du visiteur à un tiers. Ce point relève du RGPD et mérite une Issue séparée (héberger les polices localement, à vérifier dans la documentation de chaque outil).

## Ce qu'une migration demanderait

Éléments confirmés par la [page de compatibilité de la configuration de Zensical](https://zensical.org/compatibility/configuration/) :

- Zensical lit le `mkdocs.yml` existant, qu'on peut conserver « aussi longtemps que souhaité » ; la page ne donne aucune date de fin de ce support.
- L'option `hooks` n'est pas gérée (le projet n'en utilise pas).
- Les commandes `gh-deploy` et `get-deps` n'existent pas (le projet publie déjà par l'action officielle GitHub Pages).
- La variante de thème se règle par `theme: variant: classic` ou `modern`.
- Le format natif est `zensical.toml`, qui prend le pas sur `mkdocs.yml` s'il existe (information issue d'une recherche web, non lue sur une page officielle).

## Risques

| Risque | Gravité | Remarque |
|---|---|---|
| Logiciel en alpha (0.0.x) : options ou comportements qui changent d'une version à l'autre | Moyenne | Épingler la version exacte dans `pyproject.toml` et `uv.lock` |
| Plugins non couverts (versionnage `mike`, `mkdocs-typedoc`, `llmstxt`) d'après des retours d'utilisateurs | Faible aujourd'hui | Le projet n'utilise que `search` |
| Aucune garantie de durée pour la lecture du `mkdocs.yml` | Faible | Conversion en `zensical.toml` prévue plus tard par l'équipe |
| Rester sur Material : plus de correctifs de sécurité après le 5 novembre 2026 | Moyenne à terme | Site statique sans données utilisateur, mais la recherche exécute du JavaScript chez le visiteur |
| Rendu et libellés différents (variante `modern`, ancres en anglais) | Faible | Variante `classic` disponible |

## Options

| Option | Avantages | Inconvénients |
|---|---|---|
| A. Rester sur Material épinglé | Aucun travail ; rendu connu | Plus de maintenance après le 5 novembre ; la dette reste à payer plus tard |
| B. Migrer maintenant vers Zensical | Outil maintenu ; build plus rapide ; site plus léger ; essai concluant | Alpha ; accessibilité et recherche à valider dans un navigateur |
| C. Migrer plus tard (par exemple fin du sprint 4) | Laisse mûrir Zensical | Entre-temps, usage d'un outil sans maintenance |

## Recommandation

Je recommande l'**option B en deux temps**, avec la variante `classic` pour limiter les changements visibles : d'abord une PR de migration avec contrôle visuel et d'accessibilité (contraste, clavier, lecteur d'écran, recherche en français), puis fusion si le contrôle est bon, peu après le 5 novembre. Arguments : l'essai passe en mode strict sans modifier `mkdocs.yml`, le retour en arrière est trivial (le `mkdocs.yml` reste valide pour les deux outils), le site est petit et sans plugin, et rester sur un outil sans maintenance finira par coûter plus cher. Si le contrôle révèle un problème d'accessibilité, l'option A (Material épinglé) reste un repli sans urgence.

**La décision reste au développeur.** Elle sera consignée dans `JOURNAL.md` et dans le mémo oral.

## Étapes concrètes d'une migration (non appliquées)

1. Dans `pyproject.toml`, groupe `docs` : remplacer `mkdocs-material` et `mkdocs` par `zensical` épinglé sur une version exacte, puis relancer `uv lock`.
2. Optionnel : ajouter `variant: classic` sous `theme:` dans `mkdocs.yml`.
3. Dans `.github/workflows/docs.yml`, remplacer `uv run mkdocs build --strict` par `uv run zensical build --clean --strict`. Le reste (artefact Pages, déploiement, permissions) ne change pas : la documentation officielle de Zensical utilise les mêmes actions GitHub Pages et déconseille pour l'instant les caches de CI.
4. Mettre à jour `docs/documentation.md` (outils, commandes locales, alternative écartée) ; `uv run zensical serve` remplace `mkdocs serve`.
5. Contrôler en navigateur : contraste, clavier, recherche en français, pages principales.
6. Ajouter une entrée au JOURNAL et au mémo oral.

## Sources

- [Zensical, documentation officielle](https://zensical.org/docs/)
- [Zensical, compatibilité de la configuration](https://zensical.org/compatibility/configuration/)
- [Zensical, publication sur GitHub Pages](https://zensical.org/docs/publish-your-site/)
- [Zensical sur PyPI](https://pypi.org/project/zensical/)
- [Versions de Zensical sur GitHub](https://github.com/zensical/zensical/releases)
- [Synthèse de veille du 21 octobre 2026](../veille/2026-10-21.md)

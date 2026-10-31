# Problèmes connus des mises à jour Windows (scraping)

**Issue** : #45 · **Compétences** : C1 (extraction par scraping, analyse du HTML, script structuré), C3 (homogénéisation des dates, des statuts et des versions) · **Date** : 31 octobre 2026

Cette page décrit la source de type **scraping** du projet : les problèmes connus des mises à jour Windows, publiés par Microsoft sur les pages publiques « Windows release health » de Microsoft Learn, en français (`https://learn.microsoft.com/fr-fr/windows/release-health/`).

**Utilité pour le projet** : après une mise à jour mensuelle, un MSP reçoit des vagues de tickets du type « écran noir après la mise à jour » ou « l'imprimante ne marche plus depuis ce matin ». Savoir que Microsoft a reconnu le problème aide à comprendre ces tickets, et plus tard à les regrouper.

## Résumé

- Le script télécharge sept pages (une par version de Windows suivie), analyse le HTML avec BeautifulSoup et écrit un fichier JSON Lines.
- **Aucun contenu Microsoft n'est versionné** : les données restent dans `data/raw/windows_known_issues/` (ignoré par Git) et les tests utilisent du HTML fictif.
- Il lit `robots.txt`, s'identifie par un User-Agent qui cite le dépôt, n'envoie **jamais plus d'une requête toutes les 2 secondes** et refuse les redirections vers un autre domaine.
- Il est incrémental (requête conditionnelle avec l'`ETag`) et reprenable.
- Si la structure de la page n'est pas celle attendue, il s'arrête avec une erreur explicite (code de sortie 4) au lieu d'écrire des champs vides.

## Pourquoi du scraping : ce qui a été vérifié

Le scraping est un dernier recours. L'erreur de départ sur le CERT-FR (scraper des pages alors qu'une [API JSON officielle](certfr.md) existait) a conduit à vérifier d'abord, le 31 octobre 2026, qu'aucun accès structuré gratuit n'existe ici.

| Piste vérifiée | Résultat |
|---|---|
| Liens `alternate` (RSS, Atom, JSON) dans le code source de la page | Aucun. La page ne déclare que son adresse canonique et une feuille de style. Aucune mention de flux RSS dans le HTML |
| Flux RSS officiel des pages « Windows release health » | Aucun flux officiel trouvé dans la documentation ni par recherche. Les flux qui existent sont fabriqués par des services tiers qui surveillent la page (ils scrutent la même page, sans garantie) |
| API Microsoft Graph, ressource `knownIssue` (espace `windowsUpdates`) | Existe, mais en version bêta, et réservée aux **locataires Microsoft 365 disposant d'une licence Windows Enterprise ou Éducation** et d'un rôle d'administrateur. Un abonnement payant, donc hors du périmètre à budget nul |
| Centre d'administration Microsoft 365 (page « Windows release health », notifications par courriel) | Même condition de licence et de rôle. Sa documentation précise aussi que son contenu est réservé aux clients sous licence et ne doit pas être partagé publiquement |
| Dépôt de documentation cité dans les métadonnées de la page | Le dépôt `MicrosoftDocs/windows-release-pr.fr-FR` répond 404 sans compte : non accessible. Non vérifié : s'il est privé ou supprimé |
| Contenu dépendant de JavaScript | Non. Les six problèmes de la page testée et leurs blocs de détail sont dans le HTML renvoyé par le serveur, sans section à déplier ni requête supplémentaire (vérifié sur les sept pages : autant de blocs de détail que de lignes du tableau) |

Conclusion : les pages publiques sont le seul accès gratuit, et ce sont des pages statiques. Le scraping est justifié, **sans** navigateur piloté.

## Contraintes et conditions d'utilisation

| Contrainte | Vérification | Traitement dans le script |
|---|---|---|
| Conditions d'utilisation de Microsoft Learn | Usage personnel et non commercial autorisé ; copie, publication et redistribution interdites (vérifié le 23 octobre 2026) | **Aucun contenu Microsoft dans le dépôt** : ni extrait dans la documentation, ni fixture copiée, ni exemple de sortie. Données uniquement dans `data/raw/` (ignoré par Git). En pré-production publique, afficher seulement le titre du problème et le lien vers la page Microsoft |
| `robots.txt` | N'interdit que `/*/answers/...`, `/*/opbuildpdf/`, `/*/search/?*terms`, `/api/nextsteps/*` et `/api/attachments/*` ; les pages suivies sont permises (relu le 31 octobre 2026) | Lecture au démarrage, vérification de **chaque** adresse avant la requête. Si le fichier est illisible, le script s'arrête par prudence (code 3) |
| Motifs génériques de `robots.txt` | Les règles de Microsoft utilisent `*` ; le lecteur de la bibliothèque standard Python (`RobotFileParser`) ne les comprend pas | Petit lecteur écrit pour le projet (`RobotsRules`), testé : `*`, `$`, `Allow`, règle la plus longue prioritaire |
| Débit | Aucun quota publié | Une requête toutes les 2 secondes au plus, **valeur plancher** : la configuration est refusée en dessous de 2 s |
| Identification | — | User-Agent `projet-simplon-triage-msp/0.1 (projet pedagogique de fin de formation; https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES)` |
| Redirections | — | Une redirection vers un autre domaine que celui configuré est refusée |
| Volume | Sept pages, quelques dizaines de problèmes | Un lancement complet prend environ 15 secondes (huit requêtes : `robots.txt` et sept pages) |

## Pages suivies

Les pages sont dans `config/windows_issues.yaml`. Seules celles qui existent vraiment sont gardées (vérifié le 31 octobre 2026).

| Identifiant | Version de Windows | État |
|---|---|---|
| `windows-10-22h2` | Windows 10, version 22H2 | Suivie |
| `windows-11-23h2` | Windows 11, version 23H2 | Suivie |
| `windows-11-24h2` | Windows 11, version 24H2 | Suivie |
| `windows-11-25h2` | Windows 11, version 25H2 | Suivie |
| `windows-10-1809-server-2019` | Windows 10, version 1809 et Windows Server 2019 | Suivie : Windows Server 2019 n'a pas de page propre, ses problèmes sont sur la page commune avec Windows 10 1809 |
| `windows-server-2022` | Windows Server 2022 | Suivie |
| `windows-server-2025` | Windows Server 2025 | Suivie |

**Page absente** : `status-windows-server-2019` répond HTTP 404 en français ; elle n'est pas dans la configuration. Windows 11 versions 26H1 et 26H2 existent d'après la page 24H2, mais elles n'ont pas été ajoutées (hors périmètre de l'Issue) : à ajouter dans la configuration si besoin.

Un même problème est souvent publié sur plusieurs pages (par exemple 24H2 et 25H2). Chaque page garde son enregistrement : l'identifiant est `<identifiant de page>:<numéro du problème>`. Le regroupement par numéro se fera à l'agrégation.

## Structure de la page analysée

Cette description reproduit seulement la structure des balises. Les exemples sont **fictifs**.

1. Une section « Problèmes connus » contient un **tableau récapitulatif** de quatre colonnes : Résumé, Mise à jour d'origine, Statut, Dernière mise à jour. Chaque ligne a un lien vers `#NNNNmsgdesc` (NNNN : numéro du problème).
2. Une section « Détails du problème » répète, pour chaque problème, un bloc qui commence par un `div` d'identifiant `NNNNmsgdesc`. Il contient un titre, un petit tableau avec la colonne **Historique** (lignes du type « Ouvert : date, heure PT ») et le texte, dont la liste « Plateformes affectées » (Client, Serveur).

Exemple fictif d'une ligne du tableau récapitulatif :

```
Problème fictif numéro un | Build 99999.1, KB9000001, 2026-01-02 | Résolu, KB9000002 | 2026-07-01 10:13 PT
```

## Fonctionnement

Le code est dans `src/data/windows_issues.py`, le lanceur dans `scripts/fetch_windows_issues.py`, la configuration dans `config/windows_issues.yaml`.

1. **Initialisation** : lecture de la configuration, de `robots.txt`, des enregistrements déjà sauvegardés et des `ETag` mémorisés (`state.json`). Une ligne tronquée par un arrêt brutal est écartée.
2. **Téléchargement** de chaque page suivie, avec `If-None-Match` si l'`ETag` est connu et si les enregistrements de la page sont toujours sur le disque. Réponse 304 : la page est inchangée, rien n'est reparsé.
3. **Analyse** : le tableau récapitulatif est repéré par ses en-têtes, chaque ligne est liée à son bloc de détail. Le nombre de lignes doit égaler le nombre de blocs : sinon, erreur (aucun problème visible ne peut être oublié en silence).
4. **Sauvegarde** : une ligne ajoutée par problème nouveau ou modifié, `state.json` mis à jour page par page (reprise possible). À la fin, le fichier est **compacté** : un problème modifié remplace son ancienne version.
5. **Rapport** : `data/raw/windows_known_issues/report.json` (pages, problèmes par statut, taux de remplissage des champs, échecs, durée, statut).

### Commandes

Une seule page (essai) :

```
uv run python scripts/fetch_windows_issues.py --only windows-11-24h2
```

Toutes les pages suivies (lancement quotidien prévu) :

```
uv run python scripts/fetch_windows_issues.py
```

### Codes de sortie

| Code | Signification |
|---|---|
| 0 | Succès |
| 1 | Succès partiel : certaines pages ont échoué (détail dans le rapport) |
| 2 | Configuration invalide (débit inférieur à 2 s, page inconnue dans `--only`…) |
| 3 | `robots.txt` illisible ou adresse interdite |
| 4 | **Structure de la page non reconnue** (mise en page modifiée, statut inconnu, date illisible…) |
| 5 | Échec réseau persistant |

### Gestion des erreurs

- Délai d'attente de 30 secondes par requête.
- Erreurs passagères (délai dépassé, erreur de connexion, HTTP 429 ou 5xx) : jusqu'à 3 nouvelles tentatives, avec une attente de 5, 10 puis 20 secondes. Chaque tentative respecte aussi le délai de 2 secondes.
- Une page en échec (par exemple 404) est notée dans le rapport et le traitement continue ; au bout de 3 échecs consécutifs, le script s'arrête (code 5).
- Une page dont la structure est inattendue arrête tout le traitement (code 4) : continuer reviendrait à solliciter la source pour produire des données fausses.
- Une page dont la section « Problèmes connus » n'a ni tableau ni bloc de détail est considérée comme sans problème : elle est listée dans `pages_empty` du rapport pour être vérifiée.

## Données produites

Un enregistrement par problème et par page, dans `data/raw/windows_known_issues/issues.jsonl`.

| Champ | Description | Normalisation |
|---|---|---|
| `id`, `issue_id`, `page_slug`, `windows_version` | Clé de l'enregistrement, numéro du problème, page et version de Windows (libellé de la configuration) | — |
| `title`, `summary` | Titre du problème et résumé court du tableau récapitulatif | Espaces normalisés |
| `status_raw`, `status`, `status_external` | Statut d'origine, statut normalisé et indicateur de cause externe | `status` vaut `open`, `mitigated` ou `resolved` (voir ci-dessous) |
| `originating_build`, `originating_kb`, `originating_date` | Mise à jour d'origine : build, KB et date | Dates `AAAA-MM-JJ` ; `null` si « Non applicable » |
| `resolving_kb` | KB qui résout ou atténue le problème | `null` s'il n'y en a pas |
| `published_at`, `history[]` | Première date de l'historique (publication) et toutes les entrées de l'historique | ISO 8601 en UTC |
| `last_updated_at` | Dernière mise à jour du problème | ISO 8601 en UTC |
| `platforms` | Plateformes affectées : `client` et `server` (listes de versions de Windows) | `null` si la liste est absente de la page |
| `url`, `page_url`, `extracted_at` | Adresse du problème et de la page, date d'extraction | — |

### Homogénéisation (C3)

- **Dates** : les pages donnent l'heure du Pacifique (« PT »), sous deux formes (`10:13` et `17h44`). Elle est convertie en **UTC**, avec la règle américaine de l'heure d'été (du deuxième dimanche de mars au premier dimanche de novembre). La règle est écrite à la main et testée, car `zoneinfo` n'a pas de base de fuseaux horaires sous Windows sans paquet supplémentaire. Limite : l'heure ambiguë du changement d'heure d'automne n'est pas distinguée.
- **Statuts** : « Résolu » donne `resolved`, « Atténué » donne `mitigated`, « Confirmé », « Enquête en cours », « Signalé » et « Ouvert » donnent `open`. Le suffixe « externe » (cause chez un tiers) est conservé dans `status_external`. Le libellé d'origine reste dans `status_raw`. Un libellé inconnu **arrête** le script (code 4) : deviner masquerait un changement de la page.
- **Versions** : version de Windows tirée de la configuration (le titre de la page n'a pas un format stable), build et KB en champs séparés (`KB` suivi de chiffres).

### Résultat d'une exécution réelle

Le 31 octobre 2026, l'exécution complète sur les sept pages a produit **25 problèmes en 14,1 secondes et 8 requêtes** (code de sortie 0) : 15 résolus et 10 atténués, aucun ouvert à cette date (le statut `open` n'est donc vérifié que sur du HTML fictif). Le nombre de lignes du tableau égale le nombre de blocs de détail sur chaque page.

| Champ | Renseigné sur 25 | Remarque |
|---|---|---|
| `title`, `summary`, `status`, `published_at`, `last_updated_at`, `platforms` | 25 | — |
| `originating_build`, `originating_kb`, `originating_date` | 18 | Les 7 autres problèmes indiquent « Non applicable » sur la page |
| `resolving_kb` | 8 | Aucun des 10 problèmes atténués n'a de KB de résolution ; 8 des 15 problèmes résolus en citent une |

## Tests

Les tests (`tests/test_windows_issues.py`) n'appellent pas le réseau : un transport simulé de `httpx2` répond à la place du site. Les pages sont du **HTML fictif construit par le test lui-même** (titres, KB et textes inventés) ; aucune fixture n'est copiée d'une vraie page. Ils couvrent l'analyse de tous les champs, les trois statuts et l'état « externe », les deux formats d'heure, le changement d'heure, la liste de plateformes absente ou imbriquée, une dizaine de modifications de structure qui doivent lever l'erreur, `robots.txt` (motifs `*` et `$`), la limitation du débit, les nouvelles tentatives, la redirection hors domaine, l'incrémental (`ETag`, problème modifié, ligne tronquée), le rapport et les codes de sortie.

```
uv run pytest tests/test_windows_issues.py
```

## Choix et alternatives écartées

| Choix | Raison | Alternative écartée |
|---|---|---|
| Scraping des pages publiques | Seul accès gratuit, vérifié (aucun flux, Graph réservé aux abonnés) | API Microsoft Graph : licence et rôle d'administrateur requis ; flux RSS tiers : service externe sans garantie |
| `httpx2` et BeautifulSoup, sans navigateur | Les pages sont statiques : tout est dans le HTML renvoyé | Selenium : plus lourd, plus lent et inutile sans JavaScript |
| Repérage du tableau par ses en-têtes et des blocs par `NNNNmsgdesc` | Plus stable que des positions ou des classes de style | Sélecteurs CSS sur les classes de mise en page (fragiles) |
| Contrôle croisé tableau et blocs de détail | Garantit qu'aucun problème n'est oublié en silence | Lire seulement le tableau récapitulatif |
| `ETag` pour l'incrémental | Évite de télécharger les pages inchangées, donc moins de charge sur la source | Re-télécharger tout à chaque lancement |
| Lecteur de `robots.txt` maison | La bibliothèque standard ignore les motifs `*` que Microsoft utilise | `RobotFileParser` seul (faux négatifs possibles) |
| Conversion de l'heure du Pacifique écrite à la main | Aucune dépendance supplémentaire | `tzdata` (une dépendance de plus pour une règle de deux lignes) |

## Limites

- **Mise en page** : un changement de la structure des pages arrête le script (code 4) ; l'adaptation est manuelle.
- **Pas d'historique des changements de statut** au-delà de ce que la page affiche : un problème qui disparaît de la page reste dans le fichier tel qu'il a été vu la dernière fois.
- **Seul le résumé court** du tableau est conservé, pas le texte complet des détails (contournements, symptômes) : inutile pour le tri, et moins de contenu Microsoft conservé.
- **Pages en français uniquement** : le contenu anglais, parfois plus complet, n'est pas lu.
- **Un problème publié sur plusieurs pages** donne plusieurs enregistrements, à regrouper plus tard.

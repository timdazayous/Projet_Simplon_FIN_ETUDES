# Avis de sécurité du CERT-FR (API JSON)

**Issue** : #42 · **Compétences** : C1 (extraction depuis une API REST, script structuré), C3 (homogénéisation des dates, des éditeurs et des produits) · **Date** : 23 octobre 2026

Cette page décrit une source de type **API REST** du projet (la deuxième, après [endoflife.date](endoflife.md)) : les avis de sécurité du CERT-FR, le centre gouvernemental de veille sur les vulnérabilités (ANSSI).

**Mention de la source** : les contenus du CERT-FR sont publiés sous **Licence Ouverte Etalab 2.0**. Toute réutilisation doit citer la source : « CERT-FR, ANSSI, https://cert.cyber.gouv.fr/avis/ ». Le dépôt ne contient que de courtes réponses d'exemple servant aux tests, avec cette mention (`tests/fixtures/certfr/README.md`).

## Résumé

- Le script lit la liste des avis, puis télécharge en JSON chaque avis de la période qui est nouveau ou qui a été révisé depuis le dernier lancement, et écrit un fichier JSON Lines.
- Il lit et respecte le fichier `robots.txt`, s'identifie par un User-Agent qui cite le dépôt du projet, et n'envoie **jamais plus d'une requête toutes les 2 secondes**.
- Il est **incrémental** et reprenable : un avis déjà enregistré n'est pas téléchargé de nouveau, sauf si sa date de dernière révision a changé.
- Si la réponse n'a pas la structure documentée, il s'arrête avec une erreur claire, sans écrire de champ vide.

## Pourquoi l'API JSON plutôt que le HTML ou le flux RSS

Une première version du script analysait le HTML des pages (BeautifulSoup). Elle a été remplacée le 23 octobre 2026, car le CERT-FR publie une **API officielle, décrite en OpenAPI** (`https://cert.cyber.gouv.fr/openapi.json`, version 2.0). C'est un meilleur choix pour trois raisons.

| Critère | Flux RSS | Pages HTML | API JSON (retenue) |
|---|---|---|---|
| Systèmes affectés, CVE, liens | Non (titre et résumé seulement) | Oui, dans le texte de la page | Oui, en champs séparés |
| Éditeur et produit | Non | À déduire du texte | Champs structurés (`product.name`, `product.vendor.name`) |
| Robustesse | Bonne | Fragile : un changement de mise en page casse l'analyse | Contrat documenté (OpenAPI) |
| Nombre de requêtes | Une | Une par page d'index et une par avis | Une pour la liste, une par avis |

Le flux RSS ne contient que le titre et un résumé : les systèmes affectés et les CVE, qui permettent de rattacher un ticket de sécurité à un logiciel, n'y figurent pas. L'analyse du HTML a été écartée au profit de l'API : le contrat est documenté, le format est stable, et il n'y a plus de dépendance à la mise en page du site. Selenium reste écarté : il n'y a aucun JavaScript à exécuter.

## Contraintes de la source

| Contrainte | Vérification | Traitement dans le script |
|---|---|---|
| Licence | Licence Ouverte Etalab 2.0, vérifiée dans les mentions légales le 23 octobre 2026 | Mention de la source dans la documentation et le README des fixtures |
| `robots.txt` | Interdit seulement `/pdf`, `/tar`, `/js`, `/fonts` et `/fiche/` ; `/avis/` est permis | Lecture au démarrage, vérification de **chaque** adresse avant la requête. Si le fichier est illisible, le script s'arrête par prudence (code de sortie 3) |
| Débit | Aucun quota publié | Une requête toutes les 2 secondes au plus, **valeur plancher** : la configuration est refusée en dessous de 2 s |
| Identification | — | User-Agent `projet-simplon-triage-msp/0.1 (projet pedagogique de fin de formation; https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES)` |
| Redirections | L'ancienne adresse `www.cert.ssi.gouv.fr` redirige vers `cert.cyber.gouv.fr` | Une redirection vers un autre domaine que celui configuré est refusée |
| Volume | La liste contient 17 754 avis depuis 2000 (3,7 Mo en une requête) ; 1 614 ont une dernière révision de moins de 12 mois (calcul du 23 octobre 2026) | Au rythme de 2 secondes, le premier chargement de 12 mois prend environ **une heure** (estimation, non mesurée en entier) ; ensuite, un lancement quotidien prend quelques dizaines de secondes |

## Fonctionnement

Le code est dans `src/data/certfr.py`, le lanceur dans `scripts/fetch_certfr.py`, la configuration dans `config/certfr.yaml` (adresse, User-Agent, délais, période, dossier de sortie).

1. **Initialisation** : lecture de la configuration, de `robots.txt`, et des avis déjà enregistrés. Une ligne tronquée par un arrêt brutal est écartée.
2. **Liste** : `GET /avis/json/` (une requête). Le script garde les avis dont la **dernière révision** date de moins de 12 mois (option `--months`).
3. **Sélection** : un avis est téléchargé s'il est absent de la sortie, ou si sa date de dernière révision dans la liste est postérieure à celle de la version enregistrée (avis révisé). Les avis les plus récents passent en premier, donc `--limit N` garde les N plus récents.
4. **Détail** : `GET /avis/<référence>/json/` pour chaque avis sélectionné, contrôle de la structure, mise à plat en un enregistrement.
5. **Sauvegarde** : une ligne ajoutée après chaque avis (reprise possible). À la fin, et au début du lancement suivant, le fichier est **compacté** : un avis révisé remplace son ancienne version, il reste une ligne par avis.
6. **Rapport** : `data/raw/certfr/report.json` (compteurs, durée, échecs, statut).

### Commandes

Petit essai (cinq avis du dernier mois) :

```
uv run python scripts/fetch_certfr.py --limit 5 --months 1
```

Chargement initial des 12 derniers mois (environ une heure), puis lancement quotidien identique :

```
uv run python scripts/fetch_certfr.py
```

### Codes de sortie

| Code | Signification |
|---|---|
| 0 | Succès |
| 1 | Succès partiel : certains avis ont échoué (détail dans le rapport) |
| 2 | Configuration invalide (par exemple débit inférieur à 2 s) |
| 3 | `robots.txt` illisible ou chemin interdit |
| 4 | Format de l'API inattendu : la réponse n'est pas du JSON, ou ne respecte pas la structure documentée |
| 5 | Échec réseau persistant |

### Gestion des erreurs

- Délai d'attente de 60 secondes par requête (la liste complète pèse environ 4 Mo).
- Erreurs passagères (délai dépassé, erreur de connexion, HTTP 429 ou 5xx) : jusqu'à 3 nouvelles tentatives, avec une attente de 5, 10 puis 20 secondes. Chaque tentative respecte aussi le délai de 2 secondes.
- Un avis en échec est noté dans le rapport et le traitement continue ; au bout de 3 échecs consécutifs, le script s'arrête (code 5).
- Une réponse dont la structure est inattendue arrête tout le traitement (code 4) : continuer reviendrait à solliciter la source pour produire des données fausses.

## Champs de l'API et données produites

Les champs de la source sont décrits dans l'[OpenAPI du CERT-FR](https://cert.cyber.gouv.fr/openapi.json). La **liste** (`/avis/json/`) donne pour chaque avis : `reference`, `title`, `last_revision_date`, `json_url` et `scada` (avis concernant des produits du milieu industriel). Le **détail** (`/avis/<référence>/json/`) contient :

| Champ de l'API | Description (d'après l'OpenAPI) | Champ produit |
|---|---|---|
| `reference`, `title`, `summary` | Référence (`CERTFR-AAAA-AVI-NNNN`), titre, résumé | `reference`, `title`, `summary` |
| `affected_systems[]` | Système affecté : `description` (texte au format Markdown) et `product.name`, `product.vendor.name` (« N/A » si non renseigné) | `affected_systems[]` (voir ci-dessous) |
| `risks[]` | Risques (`description`) | `risks` (liste de textes) |
| `cves[]` | `name` (identifiant CVE) et `url` | `cve` (identifiants, triés, sans doublon) |
| `vendor_advisories[]` | Bulletins des éditeurs : `title`, `url`, `published_at` | `vendor_advisories` |
| `links[]` | Autres éléments de documentation : `title`, `url` | `links` |
| `revisions[]` | Gestion de version : `description`, `revision_date` (ISO, peut être `null`) | `revisions` (dates `AAAA-MM-JJ`), `first_version_date` (plus ancienne révision) |
| `affected_systems_content` | Remarques générales sur les systèmes affectés | `affected_systems_note` |
| `content` | Contenu de l'avis (section « Solutions », Markdown) | non conservé (sans valeur pour le tri) |

Champs ajoutés par le script : `last_version_date` (date de dernière révision de la liste, sinon la plus récente des révisions), `scada`, `url` (adresse de l'API d'où vient l'enregistrement) et `extracted_at` (date d'extraction). Les dates sont toutes au format `AAAA-MM-JJ` (C3 : l'API donne `2026-10-22T00:00:00.000000`). Une date `null` reste `null`.

### Systèmes affectés : éditeur, produit et version

Pour chaque système affecté, le script garde le texte d'origine (`description`) et ajoute :

- `vendor` et `product` : les noms structurés de l'API, ou `null` si l'API indique « N/A » ; `product_slug` est le nom du produit en minuscules sans accents, séparé par des tirets (`node-js`). Le rapprochement avec les noms d'endoflife.date se fera à l'étape d'agrégation ;
- `branch`, `fixed_in` et `version_parsed` : première normalisation de la version, tirée de la description. Deux formulations, les plus fréquentes, sont interprétées : « Node.js versions 22.x antérieures à 22.23.4 » (branche `22.x`, corrigé en `22.23.4`) et « Splunk SOAR versions antérieures à 8.7.0 » (corrigé en `8.7.0`).

La règle de version est **volontairement prudente** : un correctif spécial (« and SMU … »), une borne basse (« postérieures à … »), une version de système sans « antérieures à » ou toute autre formulation laisse `version_parsed: false`, avec seulement le texte d'origine.

### Résultat d'un essai réel

Le 23 octobre 2026, `--limit 5 --months 1` a produit 5 avis en 7 requêtes et 12 secondes. Sur les 33 systèmes affectés, 31 avaient un éditeur et un produit structurés et 18 une version interprétée ; aucun avis n'était sans système affecté. Les 15 autres systèmes relèvent de formulations hors règle (par exemple « Ubuntu 26.04 LTS » ou « VIOS versions 4.1 sans le correctif … ») et sont conservés avec leur texte d'origine.

## Tests

Les tests (`tests/test_certfr.py`) n'appellent pas le réseau : un transport simulé de `httpx2` répond à la place du site. Les réponses d'exemple sont dans `tests/fixtures/certfr/` ; ce sont des copies **réduites** de réponses réelles, avec la source citée dans un `README.md` à côté (le JSON n'accepte pas de commentaires). Ils couvrent la lecture de la liste et d'un avis, les listes vides, les champs obligatoires, les noms « N/A », `robots.txt`, la limitation du débit, les nouvelles tentatives, la redirection hors domaine, l'incrémental (nouveaux avis, avis révisés, ligne tronquée), les codes de sortie et l'erreur sur format inattendu.

```
uv run pytest tests/test_certfr.py
```

## Choix et alternatives écartées

| Choix | Raison | Alternative écartée |
|---|---|---|
| API JSON officielle | Contrat documenté (OpenAPI), éditeur et produit déjà structurés, moins de requêtes | Analyse du HTML (fragile, plus de requêtes) ; flux RSS (pas de systèmes affectés ni de CVE) |
| `httpx2` pour le téléchargement | Déjà installé (le SDK du client LLM en dépend), délais explicites, transport simulé pour les tests ; déjà déclaré dans `pyproject.toml` | `requests` : équivalent, mais une dépendance de plus |
| Pas de Selenium ni de BeautifulSoup | Aucun HTML à analyser ni JavaScript à exécuter | Selenium, vu en formation |
| Date de révision de la liste pour l'incrémental | Un avis révisé est retéléchargé, sans parcourir tous les avis | Ne télécharger que les références absentes (manquerait les révisions) |
| Compactage du fichier | Une ligne par avis, mais écriture au fil de l'eau pour pouvoir reprendre | Réécrire le fichier à chaque avis (lent) ; garder les anciennes versions (doublons) |
| Arrêt sur format inattendu | Évite des données vides ou fausses et des requêtes inutiles | Continuer en ignorant les champs manquants |

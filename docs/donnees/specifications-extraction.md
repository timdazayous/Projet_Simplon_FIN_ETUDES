# Spécifications techniques de l'extraction et de l'agrégation

**Statut** : brouillon rédigé le 23 octobre 2026, à relire par le développeur · **Compétences** : C1 (spécifications techniques de l'extraction), C3 (spécifications de l'agrégation), C2 (requêtes SQL et big data)

Cette page décrit **comment** le projet récupère ses données depuis cinq sources de types différents, puis les rassemble en un **jeu de données brutes unique**. Elle couvre tout le périmètre, de la source jusqu'à ce jeu brut. Le nettoyage détaillé, la base de données du projet et l'API de données font l'objet de pages séparées.

## Objectif

Le classifieur et l'application ont besoin de trois familles de données :

- des **tickets et alertes** étiquetés, pour entraîner et évaluer le modèle ;
- des **informations de contexte** sur les logiciels et équipements cités dans les tickets : avis de sécurité, fin de support ;
- un **historique volumineux**, pour les statistiques, le suivi dans le temps et les traitements big data.

Le référentiel exige une extraction depuis **cinq types de sources** : un fichier, une API REST, une base de données, du scraping de pages web et un système big data. Chaque source ci-dessous a été choisie parce qu'elle apporte une donnée utile au projet, pas seulement pour cocher un type.

## Vue d'ensemble

| Type de source | Source retenue | Ce qu'elle apporte | État |
|---|---|---|---|
| Fichier | Jeux de tickets publics sur Hugging Face (CSV et Parquet) | Tickets réels ou réalistes, étiquetés, pour l'entraînement et le test externe | **Réalisé** (#29) |
| API REST | API publique **endoflife.date** | Dates de fin de support des systèmes et logiciels | Proposé, à valider |
| Base de données | Base **MariaDB de GLPI**, en SQL direct | Tickets, suivis et catégories de l'outil de ticketing | À réaliser après le premier démarrage de GLPI |
| Scraping | Avis de sécurité du **CERT-FR** | Logiciels touchés, versions, CVE et recommandations | À réaliser |
| Big data | **Historique Parquet** interrogé avec **Spark SQL** | Plusieurs mois de tickets et d'alertes, pour l'analyse à grande échelle | À réaliser ; volume à fixer selon le poste |

**L'API de GLPI** (API v2, OAuth2) reste utilisée : elle sert à **injecter** les tickets générés dans GLPI et à lire les tickets courants. Elle n'est pas comptée comme la source « API REST », pour que deux types d'extraction ne reposent pas sur le même outil.

## Technologies communes

| Élément | Choix | Raison | Alternative écartée |
|---|---|---|---|
| Langage | Python 3.12, dépendances gérées par uv et verrouillées dans `uv.lock` | Même environnement que le reste du projet ; installation reproductible | — |
| Appels HTTP | `httpx2` | Délais d'attente explicites ; déjà installé, car le SDK du client LLM en dépend (à confirmer à l'implémentation) | `requests`, équivalent, mais une dépendance de plus |
| Configuration | Fichiers YAML dans `config/`, secrets dans `.env` | Aucun paramètre ni secret dans le code | Valeurs en dur |
| Format brut | JSON Lines (une ligne par élément) puis Parquet pour le jeu agrégé | JSON Lines est lisible et facile à reprendre ; Parquet est compact, typé et lu nativement par Spark | CSV, sans typage et fragile avec du texte libre |
| Stockage | `data/raw/` (ignoré par Git) | Aucune donnée dans le dépôt public | — |
| Journalisation | Module `logging`, métadonnées uniquement (source, nombre d'éléments, durée, erreurs) | RGPD : jamais de contenu de ticket dans les journaux | — |

### Structure commune des scripts

Chaque script d'extraction suit le même enchaînement, exigé par C1 :

1. **Lancement** : un script dans `scripts/`, exécuté par `uv run`, avec des options en ligne de commande (`--limit`, `--resume`, etc.).
2. **Initialisation** : lecture de la configuration et des secrets, ouverture des connexions, vérifications préalables (licence, `robots.txt`, disponibilité de la source).
3. **Traitement** : extraction, filtrage et conversion vers le format commun.
4. **Gestion des erreurs** : délai d'attente sur chaque appel, nouvelles tentatives avec attente croissante pour les erreurs passagères, arrêt propre avec un **code de sortie distinct** par type d'échec.
5. **Fin et sauvegarde** : écriture des résultats et d'un **rapport d'exécution** (compteurs par motif d'exclusion, durée).

## Source 1 : fichier (jeux publics Hugging Face)

Réalisée dans #29. Le détail figure dans [Récupération et traduction des jeux publics](recuperation-traduction.md).

| Point | Spécification |
|---|---|
| Données | Tobi-Bueck/customer-support-tickets (entraînement), tasksource/it-support-tickets (test externe), decisionmodelhub/support-urgency (complément sur l'urgence) |
| Accès | Téléchargement par `huggingface-hub`, sans compte |
| Contraintes | Licence vérifiée à chaque lancement (CC BY-NC 4.0 et CC BY 4.0) ; textes en anglais, allemand, espagnol et portugais, traduits en français par OPUS-MT |
| Sortie | `data/raw/public/*.jsonl` : texte d'origine, texte traduit, étiquettes d'origine, étiquettes proposées, règle appliquée |
| Fréquence | Ponctuelle : les jeux ne changent pas |

## Source 2 : API REST (endoflife.date)

| Point | Spécification |
|---|---|
| Données | Pour chaque produit suivi (Windows Server, Windows, Ubuntu, PHP, MariaDB, PostgreSQL, Exchange…) : versions, date de sortie, fin du support actif, fin du support de sécurité, version maintenue ou non |
| Pourquoi | Le MSP traite des tickets de fin de vie d'un système, et une alerte sur un serveur prend une autre importance s'il n'est plus maintenu. Cette source donne au projet une information factuelle sur le cycle de vie des produits |
| Accès | `GET https://endoflife.date/api/v1/products/<produit>/`, réponse JSON, **sans clé ni compte** |
| Contraintes | Données publiées sous licence MIT ; `robots.txt` sans restriction ; pas de quota publié : limiter à une requête par seconde et mettre en cache |
| Sortie | `data/raw/eol/products.jsonl` : une ligne par version de produit |
| Fréquence | Hebdomadaire : les dates de fin de support changent rarement |
| Erreurs | Produit inconnu (404) consigné et ignoré ; erreurs serveur réessayées trois fois avec attente croissante |

**Alternative écartée** : l'API NVD du NIST (vulnérabilités), qui recouvre en grande partie le CERT-FR et dont les quotas sans clé sont stricts.

## Source 3 : base de données (MariaDB de GLPI)

| Point | Spécification |
|---|---|
| Données | Tickets (`glpi_tickets`), catégories (`glpi_itilcategories`), suivis (`glpi_itilfollowups`), entités clientes (`glpi_entities`), utilisateurs demandeurs (`glpi_users`, colonnes strictement nécessaires) |
| Pourquoi | C'est l'outil de ticketing du MSP simulé : les tickets générés y sont injectés, puis relus comme dans un vrai système d'information |
| Accès | MariaDB 10.11 sur `127.0.0.1:3307`, avec un **compte dédié en lecture seule** (`SELECT` sur la base `glpi` uniquement), dont le mot de passe est dans `.env` |
| Requêtes | SQL écrit à la main, versionné dans `sql/`, avec jointures entre tickets, catégories et entités, et filtre sur la date de modification pour une **extraction incrémentale** |
| Contraintes | Schéma de plusieurs centaines de tables, documenté sur dbdocs.io ; moteur MariaDB alors que la base du projet est PostgreSQL, d'où une vraie transformation entre moteurs ; données personnelles dans le texte libre |
| RGPD | Pseudonymisation des personnes et masquage des secrets **à l'import**, avant tout autre traitement ; seules les colonnes utiles sont lues |
| Sortie | `data/raw/glpi/tickets.jsonl` |
| Fréquence | Quotidienne (simulée), incrémentale |

Les requêtes, leurs choix de sélection, de jointure et de filtrage, ainsi que leurs optimisations (index utilisés, projection des colonnes), seront documentés pour C2 avec l'Issue d'extraction.

## Source 4 : scraping (avis du CERT-FR)

| Point | Spécification |
|---|---|
| Données | Pour chaque avis (`CERTFR-AAAA-AVI-NNNN`) : date, risques, **systèmes affectés** (logiciel et versions), résumé, références CVE, liens vers les bulletins des éditeurs |
| Pourquoi | Rattacher un ticket `security` ou une alerte au logiciel concerné et aux avis récents ; c'est aussi la veille métier d'un MSP |
| Accès | Pages HTML publiques de `https://cert.cyber.gouv.fr/avis/` (l'ancienne adresse `cert.ssi.gouv.fr` redirige vers celle-ci) |
| Pourquoi du scraping et pas le flux RSS | Le flux ne contient que le titre et un résumé. Les systèmes affectés, les CVE et les recommandations ne figurent que dans la page de l'avis |
| Contraintes | Contenus sous **Licence Ouverte Etalab 2.0** (réutilisation libre avec mention de la source, vérifiée dans les mentions légales le 23 octobre 2026) ; `robots.txt` n'interdit pas `/avis/` (seuls `/pdf`, `/tar`, `/js`, `/fonts` et `/fiche/` le sont) ; **une requête toutes les 2 secondes au plus**, avec un User-Agent qui identifie le projet ; structure HTML susceptible de changer : le script échoue avec un message clair plutôt que de produire des champs vides |
| Technologie | `httpx2` pour télécharger, **BeautifulSoup** pour analyser le HTML |
| Sortie | `data/raw/certfr/avis.jsonl`, avec la date d'extraction et l'adresse de la page |
| Fréquence | Quotidienne, incrémentale : seuls les avis absents de la sortie sont téléchargés |

**Alternative écartée** : Selenium, vu en formation, mais inutile ici car les pages sont du HTML statique, sans JavaScript à exécuter. Il est plus lourd (navigateur à piloter) et plus lent.

## Source 5 : big data (historique Parquet et Spark SQL)

| Point | Spécification |
|---|---|
| Données | Historique de tickets et d'alertes sur plusieurs mois, produit par le générateur (#26) à un volume bien supérieur au corpus d'entraînement |
| Pourquoi | Les statistiques de tri (volumes par catégorie, par client, par période, taux d'automatisation) se calculent sur l'historique complet, trop gros pour être traité confortablement en mémoire |
| Stockage | Fichiers Parquet **partitionnés par mois** (`data/bigdata/tickets/mois=AAAA-MM/`) |
| Traitement | **PySpark** et **Spark SQL** dans un conteneur Docker, comme dans le TP de formation |
| Requêtes | Agrégations par période, catégorie et client ; documentation des optimisations pour C2 : filtre sur la partition, projection des seules colonnes utiles, filtres poussés jusqu'au format Parquet |
| Contraintes | Poste sans GPU, 15 Go de RAM : mémoire de Spark limitée et volume calibré sur une mesure. **Volume cible à décider** avec le développeur (décision encore ouverte) |
| Sortie | Tables d'agrégats en Parquet, et extraits vers le jeu agrégé |

## Agrégation en un jeu de données brutes unique (C3)

Les cinq sources ne décrivent pas toutes la même chose : il faut d'abord fixer **ce que l'on rassemble**.

| Ensemble | Sources | Clé |
|---|---|---|
| **Tickets et alertes** | Jeux publics, GLPI (SQL), historique big data | Identifiant d'origine préfixé par la source (`PUB-`, `GLPI-`, `GEN-`) |
| **Référentiel des produits** | endoflife.date, CERT-FR | Nom de produit normalisé (par exemple `windows-server`) et version |

Le jeu de données brutes unique est une table Parquet de tickets et d'alertes au **schéma commun**. Les informations de produit y sont rattachées par jointure lorsqu'un ticket cite un produit connu : fin de support atteinte, avis de sécurité récent.

| Champ du schéma commun | Description |
|---|---|
| `id`, `source`, `origin_id` | Identifiant unique, source d'origine, identifiant dans la source |
| `created_at` | Date au format ISO 8601, en UTC |
| `channel` | Canal d'entrée (taxonomie) |
| `subject`, `body` | Texte en français, **pseudonymisé** |
| `language_source` | Langue d'origine avant traduction |
| `category`, `type`, `priority`, `team` | Étiquettes de la taxonomie, ou vides si inconnues |
| `label_origin` | D'où vient l'étiquette : générateur, règle de correspondance, saisie dans GLPI |
| `products` | Produits cités (nom normalisé, version) |
| `product_eol`, `security_advisories` | Rattachement à endoflife.date et au CERT-FR |

Règles d'homogénéisation :

- dates converties en UTC au format ISO 8601 ;
- texte en UTF-8, retours à la ligne normalisés, langue française ;
- étiquettes ramenées à la taxonomie (`config/taxonomy.yaml`), sinon laissées vides et comptées ;
- doublons supprimés (même texte normalisé) ;
- entrées vides ou corrompues écartées et **comptées par motif** dans le rapport d'exécution.

## Sécurité et RGPD

- **Secrets** (compte SQL en lecture seule, client OAuth de GLPI) uniquement dans `.env`.
- **Pseudonymisation et masquage des secrets à l'import**, avant tout stockage dans le jeu agrégé ou envoi à un service externe.
- **Aucune donnée personnelle** n'est collectée sur le CERT-FR ni sur endoflife.date (contenus techniques publics).
- **Respect des sources** : licences vérifiées, `robots.txt` respecté, débit limité, User-Agent identifiable.

## Découpage prévu

| Étape | Dépend de | Issue |
|---|---|---|
| Source 2 : extraction endoflife.date | Validation du choix | À créer |
| Source 4 : scraping du CERT-FR | — | À créer |
| Injection des tickets générés dans GLPI (API v2) | Premier démarrage de GLPI | À créer |
| Source 3 : extraction SQL de GLPI | Injection | À créer |
| Source 5 : historique Parquet et Spark SQL | Décision sur le volume | À créer |
| Agrégation en un jeu unique | Les cinq sources | À créer |

## Points à valider par le développeur

- Remplacer l'API de GLPI par **endoflife.date** comme source « API REST ».
- Liste des produits suivis sur endoflife.date (proposition : ceux du parc simulé et de la stack du projet).
- Volume de l'historique big data, à fixer après une mesure sur le poste.

# Extraction des dates de fin de support (endoflife.date)

**Issue** : #41 · **Compétences** : C1 (extraction depuis une API REST, script structuré, filtrage et parsing programmés), C3 (homogénéisation des dates et des noms de produits) · **Date** : 23 octobre 2026

Cette page décrit la source « API REST » du projet : les dates de fin de support des systèmes et logiciels, récupérées depuis l'API publique [endoflife.date](https://endoflife.date). Elle complète la [spécification de l'extraction](specifications-extraction.md) (section « Source 2 »).

## Résumé

- 23 produits sont suivis (systèmes, messagerie, virtualisation, bases de données, outils de la stack du projet), listés dans `config/eol_products.yaml`.
- Une exécution réelle du 23 octobre 2026 a produit **499 versions** en **20 secondes** (21 requêtes, la limite étant d'une requête par seconde).
- Le script respecte la source : une requête par seconde au plus, un User-Agent qui identifie le projet, un cache local d'une journée.
- Les erreurs sont traitées : produit inconnu (404) consigné et ignoré, erreurs serveur et délais d'attente réessayés trois fois avec une attente croissante, sortie atomique.
- Les tests (27 cas) utilisent des réponses HTTP simulées : aucun appel réseau.

## Contraintes de la source

| Point | Constat (vérifié le 23 octobre 2026) |
|---|---|
| Accès | `GET https://endoflife.date/api/v1/products/<produit>/`, réponse JSON, sans clé ni compte |
| Licence | MIT. L'attribution « Données endoflife.date, licence MIT » figure dans la configuration et dans cette page |
| `robots.txt` | `User-agent: *` puis `Allow: /` : aucune restriction |
| Quota | Aucun quota publié. Par politesse : une requête par seconde au plus, cache d'une journée, un User-Agent explicite |
| Produit inconnu | Réponse **404 avec une page HTML** (pas du JSON) : le script ne lit le corps qu'en cas de réponse 200 |
| Fréquence de mise à jour | Les dates changent rarement : une extraction hebdomadaire suffit |

## Dépendances et installation

Aucune installation supplémentaire : `uv sync --locked` suffit, la CI aussi.

| Dépendance | Rôle | Remarque |
|---|---|---|
| `httpx2` | Appels HTTP (délai d'attente, transport simulé pour les tests) | Déjà installée pour le SDK du client LLM ; **déclarée explicitement** dans `pyproject.toml` pour ne pas dépendre d'une dépendance indirecte |
| `pyyaml` | Lecture de la configuration | Déjà présente |

**Pourquoi `httpx2` et pas `httpx` ou `requests`.** `httpx2` reprend l'interface de `httpx` (`Client`, `Timeout`, `MockTransport`…). Son API a été vérifiée à l'implémentation : le client à délai d'attente configurable et le transport simulé `MockTransport` fonctionnent comme attendu, ce qui permet des tests sans réseau. Alternative écartée : ajouter `httpx` ou `requests`, qui doubleraient une dépendance déjà installée.

## Commandes

```
uv run python scripts/fetch_eol.py
uv run python scripts/fetch_eol.py --only ubuntu php
```

| Option | Rôle |
|---|---|
| `--only P1 P2` | Ne récupère que ces produits (ils doivent figurer dans la configuration) |
| `--config FICHIER` | Autre fichier de configuration (`config/eol_products.yaml` par défaut) |

Sorties, toutes dans `data/raw/eol/` (dossier ignoré par Git, aucune donnée n'est versionnée) :

| Fichier | Contenu |
|---|---|
| `products.jsonl` | Une ligne par version de produit |
| `report.json` | Rapport d'exécution : produits traités, introuvables, en échec, depuis le cache, nombre de versions, requêtes, nouvelles tentatives, durée |
| `cache/<produit>-<AAAA-MM-JJ>.json` | Réponse brute d'un produit pour la journée : un second lancement le même jour ne refait aucune requête |

### Codes de sortie

| Code | Signification |
|---|---|
| 0 | Tout s'est bien passé |
| 1 | Des produits manquent (404 ou erreurs après nouvelles tentatives), les autres sont enregistrés |
| 2 | Configuration invalide ou option `--only` hors configuration |
| 3 | Rien n'a pu être extrait (source injoignable). Le fichier `products.jsonl` précédent est conservé |

## Configuration

Le fichier `config/eol_products.yaml` contient les paramètres HTTP (délai d'attente de 10 s, intervalle minimal de 1 s, 3 nouvelles tentatives, attente de 2 s doublée à chaque fois), le User-Agent, le dossier de sortie et la liste des produits. Le script refuse un intervalle inférieur à une seconde et une liste de produits vide ou avec doublons.

### Produits suivis

Les identifiants ont été vérifiés dans l'API le 23 octobre 2026.

| Famille | Identifiants |
|---|---|
| Systèmes d'exploitation | `windows-server`, `windows`, `ubuntu`, `debian`, `rhel`, `macos` |
| Messagerie, bureautique, virtualisation, sauvegarde, pare-feu | `msexchange`, `mssqlserver`, `office`, `esxi`, `proxmox-ve`, `veeam-backup-and-replication`, `fortios` |
| Stack du projet | `postgresql`, `mariadb`, `mysql`, `php`, `python`, `nginx`, `grafana`, `docker-engine`, `nodejs`, `redis` |

Noms écartés ou introuvables :

- `exchange-server` : réponse 404. L'identifiant correct est `msexchange`.
- Meraki et Hyper-V : absents de la liste des produits de l'API, donc non suivis.
- GLPI : absent de l'API, donc non suivi.

## Champs de `products.jsonl`

| Champ | Type | Description |
|---|---|---|
| `product` | texte | Identifiant normalisé du produit (minuscules, par exemple `windows-server`) |
| `product_label` | texte | Nom lisible (par exemple « Microsoft Windows Server ») |
| `category` | texte | Catégorie de l'API (`os`, `db`, `app`…) |
| `version` | texte | Nom de la version ou de la branche (par exemple `2022`, `26.04`) |
| `version_label` | texte | Libellé complet de la version |
| `codename` | texte ou `null` | Nom de code (par exemple « Resolute Raccoon ») |
| `release_date` | date ISO 8601 ou `null` | Date de sortie |
| `active_support_end` | date ISO 8601 ou `null` | Fin du support actif |
| `security_support_end` | date ISO 8601 ou `null` | Fin du support de sécurité : date de fin de vie |
| `extended_support_end` | date ISO 8601 ou `null` | Fin du support étendu payant, quand il existe |
| `is_lts` | booléen | Version à support long |
| `is_maintained` | booléen | Version encore maintenue au jour de l'extraction |
| `latest_version` | texte ou `null` | Dernière révision connue de la version |
| `extracted_at` | date ISO 8601 | Jour de l'extraction |
| `source` | texte | Toujours `endoflife.date` |

Les libellés des étapes du support varient selon les produits (par exemple « Security Support » pour Windows, « Maintenance & Security Support » pour Ubuntu). Les champs ci-dessus ramènent ces variantes à trois dates communes, c'est l'homogénéisation de C3.

## Normalisation (C3)

| Traitement | Règle |
|---|---|
| Dates | Format ISO 8601 `AAAA-MM-JJ`. Une valeur absente, booléenne ou illisible devient `null` ; les valeurs illisibles sont comptées dans le rapport (`invalid_dates`) |
| Noms de produits | Identifiant de l'API, en minuscules et sans espace superflu |
| Version maintenue | Valeur `isMaintained` de l'API ; à défaut, l'inverse de `isEol` |
| Versions | Toujours du texte, même quand l'API renvoie un nombre |

## Gestion des erreurs

| Situation | Comportement |
|---|---|
| Réponse 404 | Produit consigné comme introuvable, ignoré, pas de nouvelle tentative |
| Erreur serveur 5xx, réponse 429, délai dépassé, coupure réseau | Trois nouvelles tentatives, après 2 s, 4 s puis 8 s ; ensuite le produit est marqué en échec |
| Autre réponse (403, JSON invalide, format inattendu) | Produit en échec, sans nouvelle tentative |
| Source injoignable | Code de sortie 3, fichier précédent conservé |
| Cache corrompu | Ignoré, le produit est redemandé |

## RGPD et journalisation

Aucune donnée personnelle : l'API publie des informations sur des produits. Les journaux ne contiennent que le nom du produit, le nombre de versions et les erreurs.

## Tests

Les tests (`tests/test_eol.py`) utilisent `MockTransport` : aucun appel réseau, aucune attente réelle (horloge et attente simulées). Ils couvrent la configuration, le parsing, la normalisation des dates, le 404, les nouvelles tentatives et leurs attentes croissantes, les délais dépassés, les réponses inattendues, la limitation à une requête par seconde, le cache d'une journée, la sortie et le code de sortie quand la source est injoignable.

```
uv run pytest tests/test_eol.py
```

## Alternative écartée

L'API NVD du NIST (vulnérabilités) recouvre en grande partie les avis du CERT-FR, et ses quotas sans clé sont stricts.

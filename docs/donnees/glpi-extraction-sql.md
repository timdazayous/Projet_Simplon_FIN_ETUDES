# Extraction SQL des tickets GLPI

Cette page décrit la source de type **base de données** du projet : les tickets sont lus directement dans la base MariaDB de GLPI, de façon incrémentale, et **pseudonymisés dès l'import**. Elle documente les requêtes, leurs choix de sélection, de jointure et de filtrage, et leurs optimisations (compétences C1, C2 et, en amorce, C4 du bloc E1). Le contexte d'ensemble est dans les [spécifications de l'extraction](specifications-extraction.md) ; l'installation de GLPI et du compte en lecture seule est dans la page [GLPI](../glpi.md).

## Vue d'ensemble

| Étape | Fichier | Rôle |
|---|---|---|
| Création du compte en lecture seule | `sql/glpi/create_reader.sql`, `scripts/create_glpi_reader.py` | Moindre privilège, une seule fois |
| Requête des tickets | `sql/glpi/tickets.sql` | Un ticket par ligne, avec catégorie, entité et nombre de suivis |
| Requête des demandeurs | `sql/glpi/requesters.sql` | Les demandeurs des tickets lus |
| Extraction et conversion | `scripts/extract_glpi_sql.py`, `src/data/glpi_sql.py` | Structure commune des scripts, schéma commun |
| Pseudonymisation et masquage | `src/data/pseudonymize.py` | HMAC à clé, masquage du texte libre |
| Sortie | `data/raw/glpi/tickets.jsonl` (ignoré par Git), `state.json`, `extraction_report.json` | Une ligne JSON par ticket |

Commandes (depuis la racine du dépôt, après la procédure de la page GLPI) :

```bash
uv run python scripts/extract_glpi_sql.py                    # incrémental : depuis la dernière extraction
uv run python scripts/extract_glpi_sql.py --full             # tout relire, fichier reconstruit
uv run python scripts/extract_glpi_sql.py --since 2026-11-01T00:00:00+00:00 --limit 50
uv run python scripts/extract_glpi_sql.py --explain          # plan d'exécution seul, aucune donnée lue
```

Codes de sortie : 0 réussite, 2 option ou configuration invalide (variable ou clé manquante), 3 accès refusé au compte en lecture seule, 4 base injoignable après les nouvelles tentatives, 5 requête refusée ou en échec.

## Bibliothèque de connexion : PyMySQL

| Critère | PyMySQL (retenue) | Connecteur MariaDB officiel | mysql-connector-python | SQLAlchemy |
|---|---|---|---|---|
| Installation | Python pur, aucune compilation | Demande la bibliothèque C MariaDB Connector/C : pénible sous Windows et en CI | Python pur | Couche de plus, plus un pilote |
| Requêtes paramétrées | Oui (`%(nom)s`) | Oui (`?`) | Oui | Oui |
| Licence | MIT | LGPL | GPL avec exception | MIT |
| Utilité ici | Suffisant : quelques requêtes écrites à la main | Plus rapide, inutile pour quelques centaines de lignes | Équivalent, licence moins simple | Un ORM n'apporte rien à des requêtes SQL écrites à la main, et le référentiel demande justement du SQL |

PyMySQL est dans les dépendances principales (et non dans un groupe optionnel) pour que les tests s'exécutent aussi dans la CI, qui n'installe que ces dépendances.

## Compte en lecture seule

Voir la [procédure](../glpi.md#creer-le-compte-en-lecture-seule-et-la-cle-de-pseudonymisation). Trois barrières empêchent l'extraction d'écrire :

1. le compte n'a que le droit `SELECT`, sur six tables, et sur trois colonnes seulement de `glpi_users` ;
2. la session est ouverte en transaction **en lecture seule** (`SET SESSION TRANSACTION READ ONLY`) ;
3. les requêtes sont écrites à la main et versionnées : aucune requête n'est construite à partir de données.

## Requête des tickets (`sql/glpi/tickets.sql`)

```sql
SELECT t.id, t.date, t.date_mod, t.name, t.content, t.status, t.type, t.priority,
       t.externalid, c.code AS category_code, e.name AS entity_name,
       (SELECT COUNT(*) FROM glpi_itilfollowups AS f
         WHERE f.itemtype = 'Ticket' AND f.items_id = t.id) AS followup_count
FROM glpi_tickets AS t
LEFT JOIN glpi_itilcategories AS c ON c.id = t.itilcategories_id
LEFT JOIN glpi_entities AS e ON e.id = t.entities_id
WHERE t.is_deleted = 0
  AND t.date_mod >= %(since)s
ORDER BY t.date_mod, t.id
LIMIT %(limit)s
```

(Le fichier réel contient en plus des commentaires, que le script retire avant l'exécution : un `%` dans un commentaire fausserait la liaison des paramètres.)

### Choix, au regard de l'objectif

L'objectif est d'obtenir, pour chaque ticket modifié depuis la dernière extraction, de quoi alimenter le classifieur (texte, étiquettes saisies) et l'analyse (client, ancienneté, activité).

| Décision | Justification | Alternative écartée |
|---|---|---|
| **Colonnes listées une à une** | Minimisation RGPD et moins de données transférées. Les colonnes qui contiennent des données personnelles (aucun identifiant de personne n'est lu ici) ou sans utilité (SLA, durées, validations…) ne sont pas lues. | `SELECT *` : une quarantaine de colonnes de `glpi_tickets`, dont la plupart ne servent pas |
| **`LEFT JOIN` vers la catégorie et l'entité** | Un ticket sans catégorie (`itilcategories_id = 0`) ou rattaché à une entité supprimée doit rester dans l'extraction : il sera compté « sans catégorie » plutôt que perdu. Avec un `INNER JOIN`, ces tickets disparaîtraient en silence, ce qui contredit l'exigence de récupérer toutes les données visées. | `INNER JOIN` |
| **Jointures sur la clé primaire** | `c.id` et `e.id` sont des clés primaires : chaque jointure ramène au plus une ligne, donc ne multiplie pas les lignes. | — |
| **Catégorie lue par son `code`** | Le `code` de la catégorie ITIL porte la clé de la taxonomie (`network`, `backup`…) écrite par l'injection. Le libellé peut être renommé dans GLPI sans casser l'extraction. | Lire `c.name` et le comparer à des libellés |
| **Nombre de suivis par sous-requête corrélée** | La sous-requête ne renvoie qu'un nombre et s'appuie sur l'index `item (itemtype, items_id)`. | `LEFT JOIN` sur `glpi_itilfollowups` avec `GROUP BY` : dupliquerait les lignes avant de les regrouper |
| **Demandeurs dans une requête séparée** | Un ticket peut avoir plusieurs demandeurs. Les joindre ici dupliquerait les tickets. `requesters.sql` les lit par lots de 500 tickets. | `GROUP_CONCAT` : plus compact, mais limité en longueur et plus difficile à tester |
| **`is_deleted = 0`** | Exclut les tickets mis à la corbeille dans GLPI. | Les lire puis les filtrer en Python : transférer des données inutiles |
| **`ORDER BY date_mod, id`** | Ordre déterministe : `--limit` prend toujours les plus anciens changements, et la reprise se fait là où l'extraction s'est arrêtée. | Aucun tri : un `LIMIT` serait arbitraire |
| **Paramètres liés** (`%(since)s`, `%(limit)s`) | Le pilote envoie les valeurs séparément de la requête : aucune injection SQL possible. Les tests vérifient qu'aucune date n'apparaît dans le texte de la requête. | Concaténer la date dans la chaîne (OWASP : injection) |

### Requête des demandeurs (`sql/glpi/requesters.sql`)

`glpi_tickets_users` relie un ticket à ses acteurs ; `type = 1` désigne les demandeurs (2 : techniciens, 3 : observateurs). Un `LEFT JOIN` vers `glpi_users` récupère le prénom et le nom, uniquement pour **masquer ces noms dans le texte libre** : ils ne sont jamais écrits dans la sortie. Un demandeur sans compte (`users_id = 0`) est identifié par son `alternative_email`. Le nombre de marqueurs `%s` dans `IN (…)` est construit par le script ; les identifiants, eux, sont toujours liés par le pilote.

## Extraction incrémentale

- **Filtre** : `date_mod >= since`. `since` est, dans l'ordre, l'option `--since`, sinon la date de modification la plus récente de l'extraction précédente (fichier `state.json`), sinon le début de 1970 (première extraction complète). `--full` ignore l'état et reconstruit le fichier.
- **Borne incluse (`>=` et non `>`)** : plusieurs tickets peuvent partager la même seconde. La relecture du dernier instant évite d'en perdre un modifié dans la même seconde que l'extraction précédente ; en contrepartie, quelques tickets sont relus. Le fichier de sortie est mis à jour **par identifiant** (un ticket relu remplace l'ancienne ligne), donc il n'y a pas de doublon.
- **État enregistré seulement après l'écriture réussie** : si la requête échoue, l'extraction suivante repart du même point. Un fichier d'état illisible déclenche une extraction complète plutôt qu'une perte de données.
- **Fuseau horaire** : la session est ouverte en UTC (`SET time_zone = '+00:00'`), donc les colonnes `TIMESTAMP` sont lues en UTC et écrites au format ISO 8601 avec décalage.
- Dans l'injection, GLPI fixe `date_mod` à l'instant de l'injection : une extraction incrémentale relit donc les tickets injectés depuis la dernière fois, ce qui simule un flux quotidien.

## Optimisations

| Optimisation | Effet attendu | Vérification |
|---|---|---|
| Filtre sur `date_mod` (colonne indexée : `KEY date_mod`) | Ne lire que les lignes modifiées depuis la dernière extraction, sans parcourir toute la table | Plan `EXPLAIN` ci-dessous |
| Projection des colonnes | Moins de données transférées, aucune donnée personnelle inutile | Lecture de la requête |
| Jointures sur clés primaires | `eq_ref` : une lecture par ticket et par table jointe | Plan `EXPLAIN` |
| Sous-requête de comptage sur l'index `item` | Comptage sans lecture des textes des suivis (index « couvrant ») | Plan `EXPLAIN` : `Using index` |
| Demandeurs lus par lots de 500 identifiants | Une requête par lot au lieu d'une par ticket, tout en gardant une liste de taille bornée | Test sur 1 201 tickets : 3 requêtes |
| Un seul aller-retour pour les tickets, lecture complète en mémoire | Convient aux volumes visés (quelques milliers de tickets) | Mesure sur l'essai réel |

### Plan d'exécution (`EXPLAIN`)

Commande : `uv run python scripts/extract_glpi_sql.py --explain` (écrit `data/raw/glpi/explain.txt`, sans lire aucune donnée).

**Plan relevé le 8 novembre 2026 sur une base de test jetable** (MariaDB 10.11.19, schéma officiel de GLPI 11.0, quelques lignes de données fictives) :

```text
id=1 | PRIMARY            | t | type=range|filter | possible_keys=date_mod,is_deleted | key=date_mod|is_deleted | rows=1 (75%) | Using index condition; Using where; Using rowid filter
id=1 | PRIMARY            | c | type=eq_ref       | possible_keys=PRIMARY             | key=PRIMARY               | ref=glpi.t.itilcategories_id
id=1 | PRIMARY            | e | type=eq_ref       | possible_keys=PRIMARY             | key=PRIMARY               | ref=glpi.t.entities_id
id=2 | DEPENDENT SUBQUERY | f | type=ref          | possible_keys=item                | key=item                  | ref=const,glpi.t.id | Using where; Using index
```

Lecture :

1. `t` : accès par plage sur l'index `date_mod` (`range`), avec un filtre sur `is_deleted` appliqué par l'identifiant de ligne (`rowid filter`) : le moteur ne lit que les tickets récents, puis écarte ceux de la corbeille.
2. `c` et `e` : `eq_ref` sur la clé primaire, la meilleure jointure possible.
3. `f` : sous-requête dépendante qui utilise l'index `item (itemtype, items_id)` et ne lit que l'index (`Using index`).

**Plans relevés le 8 novembre 2026 sur l'instance GLPI réelle** (300 tickets injectés, compte en lecture seule `glpi_reader`) :

*Extraction complète* (`--explain --full` : `since` en 1970, les 300 tickets sont retenus) :

```text
id=1 | PRIMARY            | t | type=ALL    | possible_keys=date_mod,is_deleted | key=None    | rows=300 | Using where; Using filesort
id=1 | PRIMARY            | c | type=eq_ref | possible_keys=PRIMARY             | key=PRIMARY | ref=glpi.t.itilcategories_id
id=1 | PRIMARY            | e | type=eq_ref | possible_keys=PRIMARY             | key=PRIMARY | ref=glpi.t.entities_id
id=2 | DEPENDENT SUBQUERY | f | type=ref    | possible_keys=item                | key=item    | ref=const,glpi.t.id | Using where; Using index
```

*Extraction incrémentale* (`--explain --since 2026-11-08T18:05:31`, soit 31 tickets sur 300) :

```text
id=1 | PRIMARY            | t | type=range  | possible_keys=date_mod,is_deleted | key=date_mod | rows=31 | Using index condition; Using where
id=1 | PRIMARY            | c | type=eq_ref | possible_keys=PRIMARY             | key=PRIMARY  | ref=glpi.t.itilcategories_id
id=1 | PRIMARY            | e | type=eq_ref | possible_keys=PRIMARY             | key=PRIMARY  | ref=glpi.t.entities_id
id=2 | DEPENDENT SUBQUERY | f | type=ref    | possible_keys=item                | key=item     | ref=const,glpi.t.id | Using where; Using index
```

Lecture des plans réels :

- **L'optimiseur choisit selon la part de lignes retenues.** Quand le filtre retient tout (extraction complète), ou presque tout (essai intermédiaire : 223 tickets sur 300, soit 74 %, également en `ALL`), lire la table en entier coûte moins que de passer par l'index puis de revenir chercher chaque ligne. Quand le filtre est sélectif (31 sur 300, environ 10 %), il passe par l'index `date_mod` (`range`). L'estimation de 31 lignes est exacte. L'extraction incrémentale quotidienne, qui ne relit qu'une petite part de l'historique, profite donc bien de l'index.
- **`Using filesort`** dans le plan complet : le tri `ORDER BY date_mod, id` se fait après la lecture, puisque l'index n'est pas utilisé. Sur 300 lignes, c'est sans effet. En incrémental, il disparaît : les lignes sortent déjà triées de l'index.
- Les jointures (`eq_ref`) et le comptage des suivis (`Using index`) sont identiques aux plans de la base de test.
- Aucun index n'a eu besoin d'être forcé : l'index `is_deleted`, peu sélectif, n'est jamais choisi.

## Conversion vers le schéma commun

| Champ du schéma commun | Source dans GLPI | Traitement |
|---|---|---|
| `id` | `glpi_tickets.id` | Préfixe `GLPI-` |
| `source`, `origin_id` | — / `id` | `glpi` / identifiant numérique |
| `external_ref` | `externalid` | Identifiant d'origine `GEN-T-…` pour les tickets injectés, vide sinon |
| `created_at`, `updated_at` | `date`, `date_mod` | UTC, ISO 8601 |
| `channel` | — | Vide : l'injection ne transmet pas le canal |
| `subject`, `body` | `name`, `content` | HTML converti en texte, **puis masqué** |
| `language_source` | — | `fr` |
| `category` | `itilcategories.code` | Gardée si c'est une clé de la taxonomie, sinon vide et comptée (`unknown_category`, `no_category`) |
| `type` | `type` | 1 : `incident` ; 2 : `service_request` (GLPI n'a pas de type « information ») |
| `priority` | `priority` | 5 : P1, 4 : P2, 3 : P3, 1 ou 2 : P4 |
| `team` | — | Vide : la règle de routage l'attribuera plus tard |
| `label_origin` | — | `glpi_input` (saisie dans GLPI) |
| `client` | `entities.name` | Vide pour la Root entity |
| `requesters` | `glpi_tickets_users` | Liste de **pseudonymes** |
| `followup_count`, `glpi_status` | sous-requête, `status` | Tels quels |

Les tickets sans aucun texte (sujet et corps vides) sont écartés et comptés (`skipped_empty_text`). Tous les compteurs sont dans `extraction_report.json`.

## Pseudonymisation et masquage à l'import

Aucune donnée brute n'est écrite sur disque : la conversion pseudonymise et masque **avant** l'écriture, et les journaux ne contiennent que des compteurs et des codes d'erreur (les tests vérifient qu'aucun texte de ticket n'apparaît dans les journaux).

| Donnée | Traitement | Raison |
|---|---|---|
| Identifiant d'une personne (demandeur) | **HMAC-SHA256 à clé** (`PSEUDONYMIZATION_KEY`), tronqué à 16 caractères hexadécimaux : `person-3f9a…` | Un même demandeur garde le même pseudonyme (jointures et comptages possibles), mais on ne retrouve pas la personne sans la clé. Un simple SHA-256 serait attaquable en essayant toutes les adresses connues ; la clé secrète l'empêche. |
| Adresses de courriel dans le texte | Remplacées par `[EMAIL]` | Donnée personnelle |
| Numéros de téléphone (formats français et internationaux) | `[PHONE]` | Donnée personnelle |
| Noms du demandeur connus de GLPI (prénom, nom, et chacune de leurs parties de 3 lettres ou plus) | `[NAME]`, sans tenir compte de la casse | Donnée personnelle |
| Secrets : après « mot de passe », « mdp », « password », « code d'accès », « clé », « token »…, clés d'API courantes (`sk-…`, `AKIA…`, jetons GitHub et Slack, JWT), longues chaînes hexadécimales, clés privées | `[PASSWORD]` | Ne jamais stocker un secret collé dans un ticket |

**Placeholder fixe, pas un hachage, pour les secrets, courriels et téléphones** : remplacer un secret par son hachage permettrait de le deviner par essais. Le pseudonyme à clé est réservé aux identifiants dont on a besoin de rapprocher les occurrences.

**Choix de la sur-détection** : les règles préfèrent masquer trop que pas assez (un mot après « clé » est masqué même si ce n'est pas un secret). Pour des textes destinés à l'entraînement, perdre un mot coûte moins qu'une fuite.

### Gestion de la clé

- Générée une fois (procédure dans la page GLPI), 256 bits, dans `.env` uniquement ; refusée si elle fait moins de 32 caractères.
- Sauvegardée hors du dépôt. Changer ou perdre la clé change tous les pseudonymes : les extractions déjà faites ne se rapprochent plus des nouvelles. Si la clé fuit, il faut la remplacer et refaire une extraction complète (`--full`).

### Limites connues

- **Un nom qui n'est pas connu de GLPI n'est pas détecté.** Les règles ne reconnaissent pas un nom de personne dans un texte libre : cela demanderait un modèle de reconnaissance d'entités nommées. Dans les tickets injectés, le demandeur n'est pas un utilisateur GLPI (voir la page GLPI), donc **son nom reste dans la signature des courriels**. Ces noms sont fictifs (projet de formation, aucune donnée réelle) ; avec de vrais tickets, il faudrait soit rattacher les demandeurs à des comptes GLPI, soit ajouter une détection d'entités nommées.
- Les adresses IP ne sont pas masquées (elles servent à l'analyse des alertes ; les adresses du projet sont dans les plages de documentation réservées).
- Les formats de téléphone ou de secret non prévus passent au travers ; la liste des formats est dans `src/data/pseudonymize.py` et les tests l'élargissent à chaque cas relevé.

## Tests

`uv run --group dev pytest tests/test_glpi_sql.py tests/test_pseudonymize.py tests/test_create_glpi_reader.py` : aucun accès à une base réelle (connexion simulée).

| Domaine | Ce que vérifient les tests |
|---|---|
| Pseudonymisation | HMAC stable, insensible à la casse, dépendant de la clé et du type ; pas de collision sur 20 000 identifiants ; clé trop courte refusée sans être affichée ; les secrets et données personnelles fictifs de 400 tickets générés ont tous disparu |
| Masquage | 17 formats de courriel, téléphone et secret ; noms connus en toute casse ; mot contenant un prénom laissé intact ; texte ordinaire inchangé ; masquage idempotent |
| Requêtes | Paramétrées, `is_deleted = 0`, filtre de date, pas de `SELECT *` ; script du compte : `SELECT` seul, aucun mot de passe écrit |
| Conversion | Schéma commun, UTC, taxonomie (catégorie inconnue ou absente comptée), tickets sans texte écartés, demandeur sans compte |
| Incrémental | Reprise depuis l'état, date liée en paramètre, mise à jour sans doublon, `--full`, `--since`, `--limit`, état illisible, lots de demandeurs |
| Erreurs | Connexion impossible réessayée avec attentes croissantes (1, 2, 4 s), accès refusé sans nouvelle tentative, requête refusée (code de sortie 5), connexion toujours fermée |
| Confidentialité | Ni le disque ni les journaux ne contiennent de courriel, téléphone, secret ou nom bruts |

Un test d'intégration contre l'instance réelle n'est pas inclus : il demande le compte en lecture seule, qui n'existe qu'après la procédure manuelle.

## État de l'essai réel

**Essai du 8 novembre 2026** sur l'instance GLPI locale (GLPI 11.0.11, MariaDB 10.11.19), avec 300 tickets injectés par `scripts/inject_glpi.py`. Le compte en lecture seule et la clé de pseudonymisation ont été créés par la procédure de la page GLPI.

**Compte en lecture seule** : vérifié par trois tentatives, toutes refusées par MariaDB :

| Tentative | Résultat |
|---|---|
| `UPDATE glpi_tickets …` | refusé (erreur 1142, commande interdite) |
| `SELECT password FROM glpi_users` | refusé (erreur 1143, colonne interdite) |
| `SELECT … FROM glpi_configs` | refusé (erreur 1142, table hors périmètre) |

**Extraction complète** (`--full`), à partir de `data/raw/glpi/extraction_report.json` :

| Mesure | Valeur |
|---|---|
| Tickets lus / écrits | 300 / 300 (toutes les données visées) |
| Sans texte, catégorie inconnue, sans catégorie | 0, 0, 0 |
| Catégories retrouvées | 12 sur 12 |
| Masquages | 73 courriels, 70 téléphones, 10 secrets, 0 clé privée |
| Reprises après erreur | 0 |
| Durée | 0,2 s |
| RAM libre du poste | 4,7 Go avant, 4,8 Go après (pas d'effet mesurable) |

**Contrôles de la sortie** (`data/raw/glpi/tickets.jsonl`, hors dépôt) :

- 0 adresse électronique et 0 numéro de téléphone en clair, par recherche d'expressions régulières ;
- identifiants `GLPI-1` à `GLPI-300`, avec l'identifiant d'origine `GEN-T-…` dans `external_ref` ;
- `label_origin = glpi_input` pour les 300 tickets ;
- dates converties en UTC : GLPI stocke `date_mod` vers 19 h 05 heure de Paris, et la sortie indique `18:05:32+00:00`.

**Relance incrémentale** (sans option) : 13 tickets relus, ceux de la dernière seconde (borne `>=`), pour un total qui reste à 300. Il n'y a pas de doublon.

**Limite constatée** : `requesters_read = 0`. Les tickets injectés n'ont pas de demandeur rattaché (voir la page GLPI). Le masquage des noms n'a donc aucun nom connu à masquer, et les noms fictifs des signatures (par exemple « Sophie Lanterval ») restent en clair : aucun ticket ne contient `[NAME]`. Ces données sont générées, mais cette limite doit être levée avant tout traitement de vrais tickets (voir « Limites connues »).

## Balises de masquage

Les marqueurs écrits dans le texte suivent la convention unique du corpus (`src/data/tags.py`, voir [corpus](corpus.md)) : `[EMAIL]`, `[PHONE]`, `[NAME]` et `[PASSWORD]` (secrets et clés privées). Une balise différente de celle du corpus permettrait au modèle d'apprendre la source d'un texte plutôt que sa catégorie. Un test vérifie que toute balise produite appartient à `CONVENTION_TAGS`.

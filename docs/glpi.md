# GLPI : installation locale et accès aux données

Cette page décrit comment déployer GLPI 11 en local avec Docker, et ce qu'il faut savoir pour s'en servir comme **source de données** (compétences C1, C4, C15, bloc E1). Le choix de GLPI est justifié dans [Outil de ticketing](decisions/outil-ticketing.md).

## Rôle de GLPI dans le projet

GLPI simule le système d'information du MSP commanditaire : c'est là que les tickets sont créés et suivis. Il intervient de deux façons :

- l'**accès SQL direct** à sa base MariaDB est la source de type **base de données** du projet ;
- l'**API REST** (API v2, authentification OAuth2) sert à injecter les tickets générés et à lire les tickets courants. Depuis le 23 octobre 2026, elle n'est plus comptée comme la source « API REST » : ce rôle revient à l'API publique endoflife.date, pour que deux types d'extraction ne reposent pas sur le même outil (voir [Spécifications de l'extraction](donnees/specifications-extraction.md)).

L'application du projet ne remplace pas GLPI : elle lit ses tickets, les classe et propose de relever la priorité d'un ticket ouvert quand un message du client le justifie. Le technicien décide toujours.

## Prérequis

| Élément | Exigence |
|---|---|
| Docker | Docker Engine avec le plugin Compose v2 (`docker compose`) |
| Ressources | À mesurer au premier démarrage (voir « Mesures au premier démarrage »). Deux conteneurs : GLPI (PHP + Apache) et MariaDB. |
| Ports libres | 8082 (interface web) et 3307 (SQL), modifiables par variables |
| Fichier `.env` | Copie de `.env.example` à la racine du dépôt, avec les mots de passe renseignés |

## Ce qui est déployé

Le fichier `infra/glpi/docker-compose.yml` définit deux services :

| Service | Image (tag épinglé) | Rôle |
|---|---|---|
| `glpi` | `glpi/glpi:11.0.11` | Application GLPI 11 (image officielle) |
| `db` | `mariadb:10.11.19` | Base de données de GLPI |

**Pourquoi des tags précis** : `latest` et même `11` changent avec le temps (au moment de la rédaction, `latest` pointe déjà sur GLPI 12). Un tiers qui suit cette page obtient ainsi la même version. La mise à jour est un choix volontaire (voir plus bas). **Alternative écartée** : `glpi/glpi:latest`, non reproductible.

**Pourquoi MariaDB 10.11** : GLPI 11 exige MariaDB 10.6 ou plus récent, ou MySQL 8 ; 10.11 est une version à support long terme. **Alternative écartée** : MySQL 8 (imposé par l'exemple officiel), car MariaDB est le moteur retenu dans la décision de ticketing.

### Variables

Elles se renseignent dans le `.env` à la racine du dépôt (jamais dans le fichier compose, jamais versionnées).

| Variable | Défaut | Rôle |
|---|---|---|
| `GLPI_DB_PASSWORD` | aucun, **obligatoire** | Mot de passe de l'utilisateur de la base utilisé par GLPI |
| `GLPI_DB_ROOT_PASSWORD` | aucun, **obligatoire** | Mot de passe administrateur (`root`) de MariaDB |
| `GLPI_DB_NAME` | `glpi` | Nom de la base |
| `GLPI_DB_USER` | `glpi` | Utilisateur de la base utilisé par GLPI |
| `GLPI_HTTP_PORT` | `8082` | Port de l'interface web, sur `127.0.0.1` |
| `GLPI_DB_HOST_PORT` | `3307` | Port SQL, sur `127.0.0.1` (3307 pour ne pas gêner un MySQL local sur 3306) |

Les variables `GLPI_DB_HOST` (`db`) et `GLPI_DB_PORT` (`3306`) sont fixées dans le fichier compose : ce sont les adresses internes au réseau Docker. Les cinq variables `GLPI_DB_HOST`, `GLPI_DB_PORT`, `GLPI_DB_NAME`, `GLPI_DB_USER` et `GLPI_DB_PASSWORD` déclenchent l'**installation silencieuse** : GLPI crée seul ses tables au premier démarrage, sans assistant web. Si l'une manquait, l'assistant s'afficherait à la place.

Choisir des mots de passe longs et aléatoires, par exemple avec `openssl rand -base64 24`.

### Sécurité de la configuration

- Les deux ports sont liés à `127.0.0.1` : ni l'interface ni la base ne sont joignables depuis le réseau.
- Aucun secret n'est dans le fichier compose ; une variable obligatoire absente fait échouer la commande avec un message clair.
- Les journaux des conteneurs sont limités à 10 Mo.

### Volumes

| Volume nommé | Chemin dans le conteneur | Contenu |
|---|---|---|
| `db_data` | `/var/lib/mysql` (MariaDB) | Les données de la base |
| `glpi_data` | `/var/glpi` (GLPI) | `config`, `files` (documents joints), `logs`, `marketplace` |

Des volumes nommés (gérés par Docker) évitent les problèmes de droits sur les dossiers de la machine, notamment sous Windows.

### Attente de la base (healthcheck)

MariaDB déclare un `healthcheck` basé sur le script `healthcheck.sh --connect --innodb_initialized` fourni par l'image officielle : il vérifie que la base accepte les connexions et que InnoDB est prêt. GLPI ne démarre qu'une fois la base déclarée saine (`depends_on` avec `condition: service_healthy`), ce qui évite un échec de l'installation silencieuse sur une base pas encore prête. Le premier démarrage de MariaDB prend quelques dizaines de secondes.

## Démarrage

Depuis la **racine du dépôt** :

```bash
cp .env.example .env        # puis renseigner GLPI_DB_PASSWORD et GLPI_DB_ROOT_PASSWORD
docker compose --env-file .env -f infra/glpi/docker-compose.yml up -d
docker compose --env-file .env -f infra/glpi/docker-compose.yml ps     # les deux services doivent être « running », db « healthy »
docker compose --env-file .env -f infra/glpi/docker-compose.yml logs -f glpi   # suivre l'installation silencieuse
```

L'option `--env-file .env` est nécessaire parce que le fichier compose n'est pas à la racine : sans elle, Docker chercherait le `.env` dans `infra/glpi/`. Elle est requise pour **toutes** les commandes, y compris `ps`, `logs` et `down` : Docker Compose lit les variables du fichier à chaque commande, et les mots de passe obligatoires manquants le font échouer (« required variable GLPI_DB_PASSWORD is missing a value »). Cette erreur a été constatée au premier démarrage, le 7 novembre 2026, sur une version précédente de cette page.

Ouvrir ensuite <http://127.0.0.1:8082>.

## Premier accès et mots de passe par défaut

L'installation silencieuse crée quatre comptes avec des **mots de passe connus de tous** :

| Compte | Mot de passe par défaut | Profil |
|---|---|---|
| `glpi` | `glpi` | Super-administrateur |
| `tech` | `tech` | Technicien |
| `normal` | `normal` | Utilisateur |
| `post-only` | `postonly` | Utilisateur qui ne fait que poster des tickets |

**Obligatoire dès le premier accès, avant toute autre action** :

1. Se connecter avec `glpi` / `glpi`.
2. Créer un compte administrateur personnel (Administration > Utilisateurs) avec le profil Super-Admin et un mot de passe fort.
3. Se reconnecter avec ce compte, puis **changer le mot de passe des quatre comptes par défaut** (ou les désactiver / les supprimer, comme le recommande la documentation officielle). Ne jamais désactiver `glpi` avant d'avoir un autre super-administrateur.
4. Stocker les nouveaux mots de passe dans un gestionnaire de mots de passe, pas dans le dépôt.

Même sur une machine locale, ce réflexe fait partie de la démarche de sécurité (OWASP : identifiants par défaut).

**Points relevés au premier accès (7 novembre 2026)** :

- **Admin n'est pas Super-Admin.** Le profil Admin gère le parc et les tickets, mais pas la configuration (profils, règles, clients OAuth). Il faut donner au compte personnel une habilitation **Super-Admin** sur l'entité **Root entity**, avec **Recursive = Yes** (onglet Authorizations de l'utilisateur), puis choisir ce profil par l'avatar en haut à droite. Le profil actif y est affiché.
- **Un Admin ne peut pas attribuer un profil plus puissant que le sien.** Si `glpi` a été désactivé trop tôt, on peut le réactiver directement en base. La commande lit le mot de passe dans le conteneur, sans l'afficher :

    ```bash
    docker exec glpi-db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" glpi -e "UPDATE glpi_users SET is_active=1 WHERE name=\"glpi\";"'
    ```

- **Désactiver plutôt que supprimer.** Un compte inactif ne peut plus se connecter, mais l'historique qui lui est rattaché est conservé, et `glpi` reste disponible comme compte de secours.
- **`glpi-system` est à conserver.** C'est un compte interne de GLPI 11, utilisé pour les actions automatiques (inventaire des actifs, tâches planifiées) ; il ne sert pas à se connecter.

État retenu : un seul compte Super-Admin personnel actif ; `glpi`, `tech`, `normal` et `post-only` désactivés ; `glpi-system` conservé.

## Arrêt, mise à jour, suppression

```bash
# Arrêt (les données sont conservées dans les volumes)
docker compose --env-file .env -f infra/glpi/docker-compose.yml down

# Mise à jour : 1) sauvegarder (voir plus bas) ; 2) changer le tag de l'image dans le fichier compose ;
# 3) recréer le service. GLPI met son schéma à jour automatiquement au redémarrage.
docker compose --env-file .env -f infra/glpi/docker-compose.yml pull
docker compose --env-file .env -f infra/glpi/docker-compose.yml up -d

# Suppression COMPLÈTE, données comprises (irréversible)
docker compose --env-file .env -f infra/glpi/docker-compose.yml down -v
```

Rester sur la branche 11.0 : passer à GLPI 12 est une décision à prendre à part, car le schéma de base change entre versions majeures.

## Sauvegarde et restauration

Les données vivent dans les volumes `db_data` et `glpi_data`. Deux sauvegardes complémentaires, GLPI démarré :

```bash
# Base de données : export SQL (lisible, portable)
docker exec glpi-db sh -c 'mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" --single-transaction glpi' > glpi-backup.sql

# Données de GLPI (config, documents) : archive du volume
docker run --rm -v triage-glpi_glpi_data:/data -v "$PWD":/backup alpine tar czf /backup/glpi-data.tgz -C /data .
```

Restauration de la base : `docker exec -i glpi-db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" glpi' < glpi-backup.sql`.

Les fichiers de sauvegarde contiennent des données de tickets : ne **jamais** les committer (le dépôt est public) ; les ranger hors du dépôt.

## Accès SQL en lecture et compte dédié

La base est joignable depuis la machine hôte sur `127.0.0.1:3307` (base `glpi`). Les tables utiles pour les tickets s'appellent `glpi_tickets`, `glpi_itilcategories`, `glpi_itilfollowups`, `glpi_entities`… ; le schéma complet de GLPI 11 est documenté sur <https://dbdocs.io/glpi/GLPI-11>. Les requêtes d'extraction et leurs optimisations sont décrites dans [Extraction SQL des tickets GLPI](donnees/glpi-extraction-sql.md).

Le compte `root` de MariaDB ne sert qu'à l'administration à la main (la commande ci-dessous lit son mot de passe dans le conteneur) ; il n'est **jamais** utilisé dans du code versionné.

```bash
docker exec -it glpi-db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" glpi'
```

### Créer le compte en lecture seule et la clé de pseudonymisation

Principe du moindre privilège : les scripts d'extraction utilisent un compte qui ne peut que **lire**, et seulement six tables. Le fichier [`sql/glpi/create_reader.sql`](https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES/blob/main/sql/glpi/create_reader.sql) le crée sans jamais contenir son mot de passe : le script `scripts/create_glpi_reader.py` lit le nom et le mot de passe dans `.env` et les transmet à `mariadb` par l'**entrée standard** (un mot de passe en argument de commande serait visible dans la liste des processus).

À faire **une seule fois**, depuis la racine du dépôt, par le développeur :

1. **Générer le mot de passe du compte et la clé de pseudonymisation**, en les ajoutant à `.env` sans les afficher (la sortie est redirigée vers le fichier). Vérifier d'abord que la dernière ligne de `.env` se termine par un retour à la ligne.

    ```bash
    uv run python -c "import secrets; print(f'GLPI_DB_READER_USER=glpi_reader\nGLPI_DB_READER_PASSWORD={secrets.token_urlsafe(24)}\nPSEUDONYMIZATION_KEY={secrets.token_hex(32)}')" >> .env
    ```

    Le mot de passe fait 32 caractères et la clé 64 caractères hexadécimaux (256 bits). **Sauvegarder la clé hors du dépôt**, par exemple dans le gestionnaire de mots de passe : si elle est perdue ou changée, tous les pseudonymes changent et les anciennes extractions ne se rapprochent plus des nouvelles. Elle ne permet pas de retrouver une personne : on ne peut pas inverser un HMAC.

2. **Créer le compte** (le conteneur `glpi-db` doit tourner) :

    ```bash
    uv run python scripts/create_glpi_reader.py
    ```

    Le script affiche les droits accordés, uniquement des lignes `GRANT SELECT`. Il peut être relancé : il remet à jour le mot de passe et les droits.

3. **Vérifier** le résultat : `uv run python scripts/extract_glpi_sql.py --explain` doit réussir (le plan s'écrit dans `data/raw/glpi/explain.txt`).

Droits accordés :

| Table | Droit | Raison |
|---|---|---|
| `glpi_tickets`, `glpi_itilcategories`, `glpi_entities`, `glpi_itilfollowups`, `glpi_tickets_users` | `SELECT` | Données de l'extraction |
| `glpi_users` | `SELECT` sur les colonnes `id`, `firstname`, `realname` seulement | Les noms servent à masquer le texte libre. Le hachage du mot de passe et les jetons d'API de la table restent illisibles. |
| Toutes les autres | aucun | Configuration, jetons, mots de passe… |

Le compte est limité à 2 connexions simultanées. Son hôte est `%` parce que, vu depuis le conteneur, le client arrive avec l'adresse de la passerelle Docker et non `127.0.0.1` ; le port 3307 n'est de toute façon publié que sur `127.0.0.1`. **Alternative écartée** : `SELECT` sur toute la base `glpi`, plus simple mais qui donnerait accès aux hachages de mots de passe de GLPI.

Ces droits ont été vérifiés le 8 novembre 2026 sur une base MariaDB 10.11.19 jetable, chargée avec le schéma officiel de GLPI 11 : lecture de `glpi_tickets` acceptée, lecture de `glpi_users.password` refusée (erreur 1143), lecture de `glpi_configs` refusée (1142), `UPDATE` et `DELETE` refusés (1142).

Dépannage : si l'étape 2 échoue sans détail (le script n'affiche pas les messages d'erreur, qui pourraient citer une partie de la commande), exécuter à la main `docker exec -i glpi-db sh -c 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot glpi -e "SELECT VERSION()"'` pour vérifier que le conteneur répond.

## API v2 : mise en place et injection de tickets

Réalisé le 8 novembre 2026 (Issue #52). L'API v2 de GLPI est servie sous `/api.php/` ; la documentation interactive (Swagger) est à `/api.php/doc`, et sa version JSON à `/api.php/doc.json`. Elle utilise **OAuth2**.

### Configuration dans GLPI (faite à la main, une fois)

| Élément | Choix | Raison |
|---|---|---|
| API REST historique (v1) | **Désactivée** | Surface d'attaque réduite : un seul point d'entrée à surveiller, |
| API v2 | Activée | Seule utilisée |
| Profil `API injection` | Clone du profil Technicien, plus : Tickets (créer, lire, modifier), Catégories ITIL (créer, lire), Entités (créer, lire) | Moindre privilège : pas de suppression, pas d'administration |
| Utilisateur d'API | Compte dédié `svc-injection`, profil `API injection` sur la Root entity en récursif | Distinct du Super-Admin : si le secret fuit, les dégâts restent limités à la création de tickets |
| Client OAuth | Type d'autorisation **Password**, portée `api` seule, sans restriction d'adresse IP | Les scripts se connectent avec un utilisateur et un mot de passe. Docker présente l'hôte sous une autre adresse que `127.0.0.1`, d'où l'absence de restriction (le port n'est publié que sur `127.0.0.1`). |

Les cinq variables `GLPI_API_URL`, `GLPI_OAUTH_CLIENT_ID`, `GLPI_OAUTH_CLIENT_SECRET`, `GLPI_API_USER` et `GLPI_API_PASSWORD` sont dans `.env` (jamais dans le dépôt). Le script refuse une adresse en `http://` vers une autre machine que la machine locale, pour qu'un mot de passe ne circule jamais en clair sur un réseau.

### Ce qui a été confirmé dans le Swagger de l'instance

| Sujet | Constat |
|---|---|
| Jeton | `POST /api.php/token`, **formulaire** (`application/x-www-form-urlencoded`, pas du JSON) : `grant_type=password`, `client_id`, `client_secret`, `username`, `password`, `scope=api`. Réponse 200 : `token_type` Bearer, `access_token`, `refresh_token`, `expires_in` = 3600. |
| Ressources | Sous `/api.php/v2/…` (le préfixe `/v2` n'est pas dans l'adresse du jeton) : `/Assistance/Ticket`, `/Dropdowns/ITILCategory`, `/Administration/Entity`. |
| Création | `POST` avec un corps JSON, réponse 201 : `{"id": …, "href": …}`. |
| Lecture d'une liste | `GET` avec `start`, `limit`, `filter` (syntaxe RSQL, par exemple `external_id=like=GEN-T-*`). Réponse 200 ou **206** (contenu partiel) avec l'en-tête `Content-Range` : un 206 n'est pas une erreur. |
| Champ `external_id` | Écrivable à la création et filtrable : il porte l'identifiant d'origine `GEN-T-…`. |
| Dates `date` et `date_creation` | Écrivables : les tickets gardent leur date de création générée (janvier à mai 2026). |
| Date `date_mod` | **Non respectée** : GLPI la fixe à l'instant de l'injection. C'est utile pour l'extraction incrémentale, qui filtre sur cette colonne. |
| Priorité | GLPI la recalcule à partir de l'urgence et de l'impact. Donner la même valeur aux trois champs donne la valeur voulue (vérifié sur les 300 tickets de l'essai : aucun écart). |

L'ancienne remarque « l'ancienne API v1 reste disponible mais n'est pas utilisée » est donc remplacée : la v1 est désactivée.

### Correspondances

| Champ du projet | Champ GLPI | Valeurs |
|---|---|---|
| Priorité `P1` / `P2` / `P3` / `P4` | `priority`, `urgency`, `impact` | 5 (très haute) / 4 (haute) / 3 (moyenne) / 2 (basse). La valeur 1 (très basse) n'est jamais écrite. |
| Type `incident` | `type` | 1 (incident) |
| Types `service_request` et `information` | `type` | 2 (demande). **GLPI n'a que deux types** : la différence entre demande de service et demande d'information est perdue à l'injection, et l'extraction rend toujours `service_request`. |
| Catégorie (12) | Catégorie ITIL, champ `code` = clé de `config/taxonomy.yaml` | Reconnue par son `code` : renommer le libellé dans GLPI ne crée pas de doublon. |
| Client (60 environ) | Entité sous la Root entity | Voir « Écart constaté sur les entités ». |
| Identifiant `GEN-T-…` | `external_id` | Traçabilité entre le ticket généré et le ticket GLPI. |
| Sujet, corps | `name`, `content` | Le texte est échappé puis mis en paragraphes HTML (GLPI stocke du HTML). |
| Date de création | `date`, `date_creation` | UTC, ISO 8601 avec décalage. |
| Canal, équipe, demandeur | non transmis | Voir « Limites ». |

### Fonctionnement du script

```bash
uv run python scripts/inject_glpi.py --dry-run                 # lit GLPI, ne crée rien
uv run python scripts/inject_glpi.py --count 5                 # premiers essais
uv run python scripts/inject_glpi.py --count 300               # série complète (par défaut)
```

Options : `--env-file` (défaut `.env`), `--seed` (défaut 42), `--pool` (taille de la série générée, défaut 300), `--count` (combien de tickets de la série injecter), `--dry-run`, `--no-entities`.

**Pourquoi `--pool` et `--count` séparés.** Les identifiants `GEN-T-xxxxxx` sont numérotés dans l'ordre des dates à l'intérieur d'une série. Générer 5 tickets puis 300 donnerait des identifiants identiques pour des tickets différents. Avec une série fixe de `--pool` tickets, `--count 5` injecte les 5 premiers et `--count 300` ajoute les autres, sans doublon.

Déroulement : lecture de la configuration, génération de la série (déterministe pour une graine donnée), création des 12 catégories et des entités manquantes, lecture des `external_id` déjà présents, création des tickets absents, rapport `data/raw/glpi/injection_report.json` (compteurs seulement, jamais de contenu de ticket).

Codes de sortie : 0 réussite, 1 certains tickets en échec, 2 option ou configuration invalide, 3 jeton refusé, 4 GLPI injoignable, 5 droit manquant (403), 6 entité créée sans nom.

Choix techniques :

- **OAuth2, jeton renouvelé.** Le jeton dure une heure. Le client le renouvelle 2 minutes avant l'expiration, et une fois de plus si le serveur répond 401. Un refus du serveur de jetons (mauvais mot de passe) arrête tout sans nouvelle tentative, pour ne pas bloquer le compte.
- **Erreurs passagères.** Les erreurs 429 et 5xx ou réseau sont réessayées avec une attente qui double (2 s, 4 s, 8 s, 16 s) ; l'en-tête `Retry-After` est respecté.
- **Une création n'est jamais répétée après une erreur 5xx ou un délai dépassé** : le ticket a peut-être été créé, et le répéter le doublerait. Seuls une réponse 429 ou une connexion refusée (la requête n'est pas partie) sont réessayés. Le script étant idempotent, le relancer répare les échecs.
- **Idempotence.** Avant de créer, le script lit les `external_id` déjà présents. Relancé, il ne crée rien. **Alternative écartée** : vérifier ticket par ticket (une requête de plus par ticket).
- **Séquentiel.** Un seul appel à la fois : la durée mesurée (voir ci-dessous) ne justifie pas la complexité d'envois parallèles.

### Essai réel du 8 novembre 2026

| Mesure | Valeur |
|---|---|
| Machine | Portable Windows 11, 15,4 Go de RAM, 4,6 Go libres avant l'essai |
| Tickets injectés | 300 (graine 42), répartis du 5 janvier à début mai 2026 |
| Durée de l'injection de 280 tickets | 16,6 s, soit environ 0,06 s par ticket (283 requêtes, 1 jeton, 0 reprise, 0 échec) |
| Premiers essais | 5 tickets en 1,7 s (25 requêtes) ; 15 tickets en 1,4 s |
| Idempotence | Deuxième lancement sur les mêmes 5 tickets : 0 création, 5 « déjà présents » |
| RAM des conteneurs (`docker stats --no-stream`) | Avant : `glpi-app` 294 Mo, `glpi-db` 181 Mo. Pendant : 289 Mo et 182 Mo (CPU 65 % et 25 %). Après : 310 Mo et 183 Mo. |
| Contrôle des données | Les 300 tickets lus par l'API : 300 `external_id` distincts, priorité, type et date de création identiques à ceux générés (0 écart) |

### Écart constaté sur les entités

Les entités clientes **ne se créent pas correctement** avec le profil `API injection` : `POST /Administration/Entity` répond 201, mais l'entité lue ensuite n'a ni nom, ni commentaire, ni autre champ (tous à `null`), même sans parent. Un `PATCH` est refusé (403, droit de modification absent). Cause non établie ; hypothèses : le droit « mettre à jour » des entités manque au profil, ou anomalie de GLPI 11.0.11. À vérifier avec le développeur (essayer d'ajouter le droit de mise à jour au profil).

Conséquences :

- Le script lit l'entité qu'il vient de créer et **s'arrête au premier nom perdu** (code de sortie 6), pour ne pas fabriquer des dizaines d'entités vides.
- L'option `--no-entities` place tous les tickets dans la Root entity ; l'extraction n'a alors pas le nom du client (`client` vide).
- **Résidu de l'essai** : 12 entités sans nom (identifiants 1 à 12) ont été créées par ces essais (dont deux sondes), et les 5 premiers tickets (`GEN-T-000001` à `GEN-T-000005`) sont rattachés aux entités 1 à 5. Le profil n'a pas le droit de les supprimer ; un Super-Admin doit les nettoyer dans l'interface (Administration > Entités).

### Limites

- Le **demandeur** n'est pas créé : l'API demande l'identifiant d'un utilisateur GLPI, et le profil d'injection n'a pas le droit d'en créer. Le nom et l'adresse du demandeur restent donc dans le texte (signature), et le champ « demandeur » de l'extraction est vide pour ces tickets.
- Le **canal d'entrée** (courriel, portail…) et l'**équipe** ne sont pas transmis : ils sont vides à l'extraction.
- Les tickets sont tous au statut « Nouveau » ; le cycle de vie d'un ticket n'est pas simulé.
- Seule la racine des entités a été testée pour la création de tickets (voir ci-dessus).

## Contraintes techniques de la source (C1)

| Sujet | Contrainte |
|---|---|
| Versions | GLPI 11.0.x. MariaDB 10.6 ou plus, ou MySQL 8 (exigence de GLPI 11) ; PHP géré par l'image Docker |
| Ressources | Deux conteneurs, plus légers que l'alternative écartée (Zammad, 4 Go minimum) ; consommation réelle à mesurer au premier démarrage |
| API | API v2 sous `/api.php/`, OAuth2 obligatoire ; client à enregistrer dans l'interface ; l'ancienne API v1 est désactivée |
| Jeton | Le jeton d'accès **expire au bout d'1 heure** par défaut : le script d'extraction doit le renouveler (ou en redemander un) avant l'expiration |
| SQL | Schéma de plusieurs centaines de tables (préfixe `glpi_`) ; MariaDB alors que la base du projet est PostgreSQL : l'extraction implique une vraie transformation entre moteurs |
| Données | Les tickets contiennent du texte libre, donc potentiellement des données personnelles et des secrets : pseudonymisation et masquage **à l'import**, avant tout traitement (RGPD) |
| Installation | Installation silencieuse seulement si les cinq variables `GLPI_DB_*` sont présentes |

## Mesures au premier démarrage

Relevées le 7 novembre 2026 lors du premier démarrage réel.

| Mesure | Valeur |
|---|---|
| Date et machine | 7 novembre 2026, portable Windows 11, 15,4 Go de RAM, Docker Desktop (VM WSL limitée à 3,8 Go) |
| Durée de téléchargement des images | 37 s (image GLPI : 1,62 Go) |
| Durée jusqu'à l'état `healthy` de MariaDB | 13 s |
| Durée de l'installation silencieuse de GLPI | environ 40 s de plus, jusqu'à la première réponse de la page de connexion |
| RAM au repos (`docker stats --no-stream`) | 68 Mo pour `glpi-app`, 187 Mo pour `glpi-db` |
| Espace disque des volumes | 309 Mo pour `db_data`, 1,5 Mo pour `glpi_data` |
| Capture de l'écran de connexion | faite, conservée hors du dépôt (dossier `media/`, ignoré par Git) |

Commande de mesure : `docker stats --no-stream glpi-app glpi-db`.

**Ce qui pèse vraiment** : GLPI et MariaDB n'utilisent qu'environ 255 Mo à eux deux. La machine virtuelle de Docker Desktop réserve en revanche près de 4 Go dès son lancement. Sur ce poste, la RAM libre est descendue à 0,8 Go avec les applications courantes ouvertes, sous le seuil d'arrêt de 1 Go que s'impose le projet, puis remontée à 2 Go un peu plus tard. La stack complète (PostgreSQL, Spark, supervision) demandera donc de surveiller la mémoire, et peut-être d'arrêter GLPI quand il ne sert pas.

L'interface s'affiche en anglais par défaut ; la langue se change dans les préférences de l'utilisateur (ou pour tous dans Configuration > Générale).

## Sources

- [Docker Hub : image `glpi/glpi`](https://hub.docker.com/r/glpi/glpi) (tags, dont 11.0.11)
- [GLPI : dépôt des images Docker, README](https://github.com/glpi-project/docker-images) (variables `GLPI_DB_*`, `GLPI_SKIP_AUTOINSTALL`, volumes, port, exemple compose)
- [GLPI : Running GLPI on Docker](https://help.glpi-project.org/procedures/running_glpi_on_docker.md)
- [GLPI : README de la branche 11.0](https://github.com/glpi-project/glpi/blob/11.0/bugfixes/README.md) (MariaDB 10.6 ou plus, MySQL 8 ou plus)
- [GLPI : comptes par défaut à l'installation](https://glpi-install.readthedocs.io/en/latest/install/wizard.html)
- [GLPI : RESTful API v2](https://help.glpi-project.org/documentation/modules/configuration/general/api/restful-api-v2) (clients OAuth, `/api.php/token`, jeton d'1 heure, `/api.php/doc`)
- [Docker Hub : image officielle `mariadb`](https://hub.docker.com/_/mariadb) (tag 10.11.19, variables `MARIADB_*`, `healthcheck.sh`)
- [Schéma de base de GLPI 11](https://dbdocs.io/glpi/GLPI-11)

Points non confirmés dans la documentation officielle consultée : la consommation de mémoire de GLPI, la version de MariaDB « recommandée » (seul le minimum est publié ; 10.11 est un choix du projet), et les paramètres exacts de la requête de jeton OAuth.

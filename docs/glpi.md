# GLPI : installation locale et accès aux données

Cette page décrit comment déployer GLPI 11 en local avec Docker, et ce qu'il faut savoir pour s'en servir comme **source de données** (compétences C1, C4, C15, bloc E1). Le choix de GLPI est justifié dans [Outil de ticketing](decisions/outil-ticketing.md).

## Rôle de GLPI dans le projet

GLPI simule le système d'information du MSP commanditaire : c'est là que les tickets sont créés et suivis. Il fournit **deux des cinq sources de données** :

- l'**API REST** (API v2, authentification OAuth2), pour les tickets courants ;
- l'**accès SQL direct** à sa base MariaDB, pour l'historique.

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
docker compose -f infra/glpi/docker-compose.yml ps     # les deux services doivent être « running », db « healthy »
docker compose -f infra/glpi/docker-compose.yml logs -f glpi   # suivre l'installation silencieuse
```

L'option `--env-file .env` est nécessaire parce que le fichier compose n'est pas à la racine : sans elle, Docker chercherait le `.env` dans `infra/glpi/`. Les autres commandes `docker compose` du projet utilisent le même schéma, `--env-file .env` en plus quand elles ont besoin des variables.

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

## Arrêt, mise à jour, suppression

```bash
# Arrêt (les données sont conservées dans les volumes)
docker compose -f infra/glpi/docker-compose.yml down

# Mise à jour : 1) sauvegarder (voir plus bas) ; 2) changer le tag de l'image dans le fichier compose ;
# 3) recréer le service. GLPI met son schéma à jour automatiquement au redémarrage.
docker compose --env-file .env -f infra/glpi/docker-compose.yml pull
docker compose --env-file .env -f infra/glpi/docker-compose.yml up -d

# Suppression COMPLÈTE, données comprises (irréversible)
docker compose -f infra/glpi/docker-compose.yml down -v
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

## Accès SQL en lecture (futures extractions)

La base est joignable depuis la machine hôte sur `127.0.0.1:3307` (base `glpi`). Les tables utiles pour les tickets s'appellent `glpi_tickets`, `glpi_itilcategories`, `glpi_itilfollowups`, `glpi_entities`… ; le schéma complet de GLPI 11 est documenté sur <https://dbdocs.io/glpi/GLPI-11>. Les tables réellement utilisées seront documentées avec le modèle de données (C2).

```bash
docker exec -it glpi-db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" glpi'
```

**Prévu, non réalisé ici** : un compte MariaDB **en lecture seule** (`SELECT` uniquement sur la base `glpi`) sera créé pour les scripts d'extraction, afin de ne pas leur donner les droits du compte de GLPI (principe du moindre privilège, rôles séparés application / lecture seule). Tant qu'il n'existe pas, ne pas utiliser le compte `root` dans du code versionné.

## API v2 : étapes manuelles (décrites, non réalisées)

L'API v2 de GLPI est servie sous `/api.php/` ; la documentation interactive (Swagger) est à `/api.php/doc`. Elle utilise **OAuth2** : avant tout appel, il faut enregistrer un client.

1. Dans GLPI : **Configuration > Clients OAuth**, créer un client. GLPI génère un identifiant (`client_id`) et un secret (`client_secret`).
2. Choisir le type d'autorisation **Password**, recommandé pour les scripts automatisés. (Authorization Code est prévu pour les applications avec utilisateur ; Client Credentials ne couvre que l'inventaire.)
3. Noter `client_id` et `client_secret` **dans le `.env`** (jamais dans le dépôt). Les noms de variables seront fixés avec l'Issue d'extraction.
4. Obtenir un jeton par une requête POST sur `/api.php/token`, avec l'identifiant et le mot de passe d'un utilisateur GLPI dédié (à créer, droits minimaux) et le client OAuth. Les paramètres exacts (portées, format) sont à confirmer dans le Swagger de l'instance.
5. Tester sur un ticket créé à la main avant d'écrire le script d'extraction.

Ce qui reste à faire manuellement n'est volontairement pas automatisé ici : la création du client OAuth se fait dans l'interface et produit un secret qui ne doit pas être versionné.

## Contraintes techniques de la source (C1)

| Sujet | Contrainte |
|---|---|
| Versions | GLPI 11.0.x. MariaDB 10.6 ou plus, ou MySQL 8 (exigence de GLPI 11) ; PHP géré par l'image Docker |
| Ressources | Deux conteneurs, plus légers que l'alternative écartée (Zammad, 4 Go minimum) ; consommation réelle à mesurer au premier démarrage |
| API | API v2 sous `/api.php/`, OAuth2 obligatoire ; client à enregistrer dans l'interface ; l'ancienne API v1 reste disponible mais n'est pas utilisée |
| Jeton | Le jeton d'accès **expire au bout d'1 heure** par défaut : le script d'extraction doit le renouveler (ou en redemander un) avant l'expiration |
| SQL | Schéma de plusieurs centaines de tables (préfixe `glpi_`) ; MariaDB alors que la base du projet est PostgreSQL : l'extraction implique une vraie transformation entre moteurs |
| Données | Les tickets contiennent du texte libre, donc potentiellement des données personnelles et des secrets : pseudonymisation et masquage **à l'import**, avant tout traitement (RGPD) |
| Installation | Installation silencieuse seulement si les cinq variables `GLPI_DB_*` sont présentes |

## Mesures au premier démarrage

À compléter avec le développeur lors du premier démarrage réel (le fichier compose n'a été validé que par `docker compose config`, sans lancer de conteneur).

| Mesure | Valeur |
|---|---|
| Date et machine | _à compléter_ |
| Durée de téléchargement des images | _à compléter_ |
| Durée jusqu'à l'état `healthy` de MariaDB | _à compléter_ |
| Durée de l'installation silencieuse de GLPI | _à compléter_ |
| RAM au repos (`docker stats --no-stream`) | _à compléter_ |
| Espace disque des volumes | _à compléter_ |
| Capture de l'écran de connexion | _à ajouter (sans mot de passe visible)_ |

Commande de mesure : `docker stats --no-stream glpi-app glpi-db`. Les valeurs seront aussi reportées dans le comparatif [Outil de ticketing](decisions/outil-ticketing.md).

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

# Choix de l'outil de ticketing : GLPI ou Zammad

**Statut** : **décidé — GLPI** (2026-10-07) · **Issue** : #2 · **Compétences** : C1 (contraintes des sources), C15 (choix des outils)

## Pourquoi ce choix compte

L'outil de ticketing simule le système d'information du MSP commanditaire. Il fournit **deux des cinq sources de données** du projet :

- **API REST** : récupération des tickets courants (C1) ;
- **base de données** : requêtes SQL directes sur l'historique (C1, C2).

Il doit donc offrir une API documentée, un schéma de base lisible, et tourner en local avec le reste de la stack (PostgreSQL, Spark, Prometheus, Grafana…), sur CPU et sans budget.

## Les deux candidats

| | GLPI | Zammad |
|---|---|---|
| Éditeur | Teclib' (France) | Zammad GmbH (Allemagne) |
| Licence | GPL v3 | AGPL v3 |
| Orientation | Gestion de services informatiques (ITIL) et de parc | Support client multicanal (e-mail, chat, téléphone) |
| Technologie | PHP + MariaDB / MySQL | Ruby on Rails + PostgreSQL + Elasticsearch |

## Comparaison critère par critère

| Critère | GLPI | Zammad | Avantage |
|---|---|---|---|
| **Proximité avec un MSP** (Autotask) | Tickets ITIL, catégories, parc matériel, contrats, SLA, entités par client | Tickets, groupes, organisations ; pas de gestion de parc native | GLPI |
| **Urgence et priorité** | Matrice native urgence × impact → priorité, comme dans un outil ITSM | Priorités simples | GLPI |
| **API REST** | API v2 (« High-level API ») avec **OAuth2** (grant *password* pour les scripts) et doc Swagger intégrée ; l'API v1 historique reste disponible | API REST mature, authentification par jeton, très bien documentée | Zammad légèrement (plus simple) ; GLPI plus riche à présenter (OAuth2) |
| **Accès SQL direct** | MariaDB, schéma volumineux mais nommé clairement (`glpi_tickets`, `glpi_itilcategories`, `glpi_itilfollowups`…) | PostgreSQL uniquement depuis la version 7.0 (mars 2026) | Égalité |
| **Diversité des sources** | MariaDB comme source, PostgreSQL comme base du projet : deux SGBD, donc une vraie étape de transformation entre moteurs | Même moteur que la base du projet | GLPI |
| **Ressources (RAM)** | Léger : un conteneur PHP + un conteneur MariaDB | **Au moins 4 Go exigés**, surtout à cause d'Elasticsearch, plus un réglage système (`vm.max_map_count`) | GLPI |
| **Installation Docker** | Images officielles `glpi/glpi` sur Docker Hub, installation silencieuse par variables `GLPI_DB_*` | `docker compose` officiel complet (plusieurs services) | Égalité |
| **Éco-responsabilité** | Empreinte mémoire et CPU faible | Elasticsearch gourmand en permanence | GLPI |
| **Crédibilité devant le jury** | Très répandu dans les PME et les collectivités françaises | Moins connu en France | GLPI |
| **Ergonomie** | Interface plus datée | Interface moderne | Zammad |

## Contraintes techniques identifiées (C1)

**GLPI**
- Il faut enregistrer un **client OAuth** dans l'interface (Configuration > Clients OAuth) avant tout appel à l'API v2. Le jeton d'accès expire au bout d'une heure par défaut : le script d'extraction doit le renouveler.
- GLPI 11 demande MariaDB 10.6 ou plus récent, ou MySQL 8.
- Le schéma compte plusieurs centaines de tables : il faudra documenter précisément celles que l'on utilise (C2).

**Zammad**
- Elasticsearch est optionnel en théorie, mais activé par défaut et nécessaire à l'initialisation du conteneur.
- Il faut au moins 4 Go de RAM réservés, en plus du reste de la stack sur la même machine.

## Recommandation

**GLPI**, pour trois raisons principales :

1. **Il ressemble davantage au métier d'un MSP** : parc, contrats, entités clientes et matrice urgence × impact. Cette matrice servira directement à définir les niveaux d'urgence de la taxonomie (#6).
2. **Il est plus léger**, ce qui compte sur un poste qui fera aussi tourner Spark, PostgreSQL et le monitoring. C'est aussi un argument d'éco-responsabilité.
3. **Il diversifie les sources** : extraire depuis MariaDB pour charger dans PostgreSQL montre la maîtrise de deux SGBD (C1, C2, C3).

**Ce qu'on accepte en échange** : une interface moins moderne, sans impact puisque le front du projet est une application React séparée, et une API v2 récente avec moins d'exemples en ligne que celle de Zammad.

**Alternative écartée** : Zammad, très bon outil de support client, mais orienté multicanal plutôt qu'ITSM, et trop gourmand en mémoire pour notre environnement local.

## À vérifier après la décision

- Mesurer la consommation réelle de RAM de GLPI dans Docker et la noter dans la procédure d'installation.
- Tester l'API v2 (OAuth2 *password grant*) sur un ticket créé à la main avant d'écrire le script d'extraction.

## Sources

- [GLPI — RESTful API (V2)](https://help.glpi-project.org/documentation/modules/configuration/general/api/restful-api-v2)
- [GLPI — Lancer GLPI avec Docker](https://www.glpi-project.org/en/run-glpi-with-docker/)
- [GLPI 11 is out](https://www.glpi-project.org/fr/glpi-11-is-out)
- [Zammad — variables d'environnement Docker](https://docs.zammad.org/en/pre-release/_sources/appendix/environment-variables.rst.txt)
- [Communauté Zammad — besoins en mémoire](https://community.zammad.org/t/2-5-0-memory-requirements/1073)
- [Zammad — migration vers PostgreSQL](https://zammad-documentation-dvuckovic.readthedocs.io/en/latest/appendix/migrate-to-postgresql.html)
- [Communauté Zammad — fin du support MySQL / MariaDB](https://community.zammad.org/t/no-more-mysql-mariadb/10463)

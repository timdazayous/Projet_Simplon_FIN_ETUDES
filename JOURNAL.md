# Journal de projet

## 2026-10-06 — Structure initiale du dépôt
**Type** : décision
**Contexte** : démarrage du projet, besoin d'une arborescence qui reflète les blocs du référentiel (données, service IA, modèle, application).
**Choix / Cause** : dossiers `src/{api,classifier,llm,data}`, `tests/`, `docs/`, `data/`, `models/`, `scripts/` ; données et modèles exclus de Git (à versionner plus tard avec DVC) ; secrets uniquement dans `.env`, avec `.env.example` maintenu à jour.
**Raison / Résolution** : séparer le classifieur maison (E3) du service LLM externe (E2) dès la structure, pour ne pas les fusionner ; éviter toute fuite de secrets ou de données personnelles dans l'historique Git.

## 2026-10-06 — Orientations techniques et organisation
**Type** : décision
**Contexte** : lecture du référentiel (E1 à E5) et cadrage avant le développement.
**Choix / Cause** : front en React ; environnement local complet en `docker compose` + pré-production gratuite allégée (API, front, Postgres) ; documentation projet avec MkDocs et API documentée en OpenAPI ; mots de passe hachés en Argon2id, données personnelles pseudonymisées (HMAC) ou chiffrées, secrets des tickets masqués à l'import ; pilotage dans GitHub Projects ; veille hebdomadaire lancée dès le début.
**Raison / Résolution** : chaque choix répond à des critères explicites (pré-production C15/C19, OpenAPI C5/C9, doc accessible transverse, RGPD C4, agile C16, veille C6). Alternatives écartées : Sphinx (plus lourd que MkDocs) ; hébergement gratuit de toute la stack (impossible, et non exigé).

## 2026-10-06 — Référentiel exclu du dépôt public
**Type** : décision
**Contexte** : le dépôt GitHub est public ; les PDF du référentiel Simplon sont des documents de formation.
**Choix / Cause** : dossier `referentiel/` ajouté au `.gitignore`.
**Raison / Résolution** : ne pas rediffuser de documents dont la diffusion publique n'est pas prévue ; ils restent consultables en local.

## 2026-10-06 — Mise en place du pilotage agile
**Type** : décision
**Contexte** : C16 exige un backlog, un kanban et un burndown disponibles tout au long du projet.
**Choix / Cause** : Scrum adapté à un développeur seul, sprints de 2 semaines ; GitHub Project lié au dépôt (statuts Backlog, À faire, En cours, En revue, Terminé ; champs Estimation en points et Sprint) ; jalons par phase ; labels par épreuve. Backlog initial de 8 Issues rédigées avec la skill `referentiel` (critères d'acceptation issus du référentiel).
**Raison / Résolution** : outil gratuit et intégré au dépôt, qui relie Issues, PR et CI. Alternatives écartées : Trello ou Jira (outil séparé du code, liens Issue/PR moins directs).

## 2026-10-07 — Outil de ticketing : GLPI
**Type** : décision
**Contexte** : l'outil de ticketing simule le SI du MSP et fournit deux sources de données (API REST, SQL direct). Le développeur n'avait utilisé ni GLPI ni Zammad.
**Choix / Cause** : GLPI 11 en Docker (images officielles, base MariaDB).
**Raison / Résolution** : plus proche du métier d'un MSP (ITIL, parc, contrats, matrice urgence × impact) ; nettement plus léger que Zammad, qui exige au moins 4 Go de RAM à cause d'Elasticsearch (argument d'éco-responsabilité et de faisabilité sur un poste qui fait aussi tourner Spark et le monitoring) ; source MariaDB distincte de la base PostgreSQL du projet. Alternative écartée : Zammad. Comparaison complète dans `docs/decisions/outil-ticketing.md`.

## 2026-10-07 — Organisation de la veille
**Type** : décision
**Contexte** : C6 exige une veille d'au moins 1 h par semaine, tracée, avec un outil d'agrégation cohérent avec les sources et le budget.
**Choix / Cause** : trois thématiques liées au projet (services LLM et modèles légers, réglementation IA et données, outils/sécurité/accessibilité) ; 14 sources évaluées selon une grille de fiabilité ; agrégateur FreshRSS auto-hébergé en Docker (`tools/freshrss/`) ; séance d'1 h le week-end ; synthèses publiées sur le site de documentation.
**Raison / Résolution** : FreshRSS est libre, gratuit, rafraîchit les flux automatiquement et s'intègre à la stack Docker. Alternatives écartées : Inoreader (offre gratuite avec publicité, flux à rafraîchir manuellement d'après l'expérience du développeur), Feedly (tri limité en gratuit).

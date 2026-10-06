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

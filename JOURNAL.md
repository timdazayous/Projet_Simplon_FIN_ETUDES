# Journal de projet

## 2026-10-06 — Structure initiale du dépôt
**Type** : décision
**Contexte** : démarrage du projet, besoin d'une arborescence qui reflète les blocs du référentiel (données, service IA, modèle, application).
**Choix / Cause** : dossiers `src/{api,classifier,llm,data}`, `tests/`, `docs/`, `data/`, `models/`, `scripts/` ; données et modèles exclus de Git (à versionner plus tard avec DVC) ; secrets uniquement dans `.env`, avec `.env.example` maintenu à jour.
**Raison / Résolution** : séparer le classifieur maison (E3) du service LLM externe (E2) dès la structure, pour ne pas les fusionner ; éviter toute fuite de secrets ou de données personnelles dans l'historique Git.

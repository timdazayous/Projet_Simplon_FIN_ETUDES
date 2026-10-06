# CLAUDE.md — Triage IA des tickets et alertes MSP

Contexte permanent du projet. Ce fichier reste **court** : les détails par domaine se chargent à la demande (voir « Routage »). Le mettre à jour dès qu'une décision est prise.

## Contexte

Projet de fin de formation **Développeur en intelligence artificielle (Simplon)**. Soutenance devant jury en **juillet 2027** ; objectif : projet **terminé début 2027**, puis peaufinage et répétitions. Le développeur est en reconversion, travaille dans un MSP (Autotask, Zabbix, Rewst) et est **débutant en front-end**. Rythme : 2 à 3 h par semaine minimum, plus quand possible.

**Commanditaire fictif** : un MSP d'une trentaine de personnes gérant une soixantaine de PME clientes.

**Problème** : des centaines de tickets et d'alertes par jour dans une file unique ; tri manuel (catégorie, urgence, équipe, cas similaires), lent et source d'erreurs de routage.

**Solution** : pour chaque ticket entrant, l'application
1. le **classe** (catégorie, urgence, équipe) via un modèle entraîné dans le projet ;
2. **suggère une piste de résolution** via un LLM, à partir des tickets résolus et de la documentation ;
3. **apprend des corrections** des techniciens (feedback → ré-entraînement).

L'outil aide le technicien à décider, il n'agit jamais seul. Pas de remédiation automatique.

## Le référentiel pilote les choix

Chaque brique existe parce qu'une compétence l'exige. Ne pas simplifier une brique sans vérifier qu'elle ne valide pas un critère.

| Bloc | Brique du projet | Points exigés souvent oubliés |
|---|---|---|
| **E1** (C1–C5) Données | Extraction 5 sources, agrégation, BDD, API de données | Spécifications techniques écrites ; requêtes SQL **et** SQL big data documentées (choix + optimisations) ; Merise ; registre RGPD + procédures de tri avec fréquence ; install reproductible |
| **E2** (C6–C8) Service IA | Groq / Ollama | Veille ≥ 1 h/semaine tracée, synthèses accessibles ; benchmark avec services **écartés** et **éco-responsabilité** ; monitoring du service |
| **E3** (C9–C13) Modèle | Classifieur maison | API sécurisée + tests de tous les endpoints ; monitoring + alertes ; tests données/entraînement/évaluation ; **CI qui ré-entraîne, évalue et livre par PR avec rapport** |
| **E4** (C14–C19) Application | Front React + API | User stories avec critères d'accessibilité (RGAA/WCAG) ; diagramme de flux de données ; **POC en pré-production** ; agile tracé (backlog, kanban, burndown) ; éco-conception ; OWASP ; CI + CD avec build de conteneurs |
| **E5** (C20–C21) Production | Monitoring + incident | Métriques + seuils d'alerte documentés ; incident réel reproduit, débogué **depuis l'outil de suivi** (Issue), corrigé par PR |

**Transverse** : toute documentation livrée doit respecter les recommandations d'accessibilité (Valentin Haüy, Microsoft).

**Livrables** : rapports professionnels E1, E2, E3, E4 + documentation E5. Rédigés **au fil de l'eau**, pas à la fin.

## Contraintes dures

- **Zéro budget** : outils gratuits ou open source uniquement.
- **Pas de GPU**, ni en local ni en CI. Entraînement sur CPU dans un runner GitHub Actions gratuit.
- **Langue** : tickets et interface en **français**.
- **RGPD** : données personnelles **pseudonymisées avant tout traitement** et **avant tout envoi externe** (Groq). Ne jamais logger de contenu de ticket brut.
- **Secrets** : uniquement dans `.env` (ignoré par Git). Maintenir `.env.example` à jour sans valeurs réelles.
- **Dépôt public** : ne jamais committer de données réelles, de secrets ni les PDF du référentiel (`referentiel/`, ignoré).

## Choix techniques actés

**Deux briques IA distinctes, ne pas les fusionner :**
- **Classifieur entraîné dans le projet** (E3) : baseline TF-IDF + régression logistique (scikit-learn), puis CamemBERT distillé si le gain est démontré. Ré-entraîné par la CI. Jamais remplacé par un service externe.
- **Service LLM existant** (E2) pour résumé et suggestion : **Groq** (free tier) en principal, **Ollama** local en secours. Une seule abstraction compatible OpenAI, fournisseur choisi par `LLM_PROVIDER=groq|ollama`. Erreurs 429 gérées (retry/backoff, repli Ollama).

**Modèles de classification « JEV-like »** (ex. modèles Ollama nimble/tev1, Cloudflare Clef) : classifieurs peu verbeux, bon marché sur gros volume, qui renvoient des scores de confiance. Uniquement **comparateurs dans le benchmark** et sujet de veille, jamais en remplacement du classifieur maison.

**Données sensibles en base** :
| Donnée | Traitement |
|---|---|
| Mots de passe utilisateurs | Hachage **Argon2id** (ou bcrypt), jamais réversible |
| Données personnelles des tickets | **Pseudonymisation** (HMAC à clé) pour entraînement et Groq ; **chiffrement réversible** si affichage nécessaire ; tables séparées dans le modèle Merise |
| Secrets collés dans les tickets | Détectés et **masqués à l'import**, jamais stockés |

Plus : clés dans `.env` uniquement, rôles PostgreSQL séparés (application / lecture seule), script de purge avec durée de conservation.

**Environnements** :
- **Local** : `docker compose` avec la stack complète (référence pour les procédures d'installation).
- **Pré-production** : hébergement gratuit allégé (API + front + Postgres). Hébergeur à choisir plus tard. D'ici là, **toute la configuration passe par variables d'environnement**.

**Documentation** : OpenAPI généré par FastAPI pour les API ; **MkDocs** pour la doc projet (Markdown → HTML accessible, publié sur GitHub Pages par la CI). Sphinx écarté (plus lourd). Thème à vérifier en veille.

**Stack** : Python 3.12 (uv), FastAPI, PostgreSQL + pgvector, PySpark / Spark SQL sur Parquet (dans Docker), DVC, MLflow, Evidently, pytest, GitHub Actions, Prometheus + Grafana, Loki, **React** pour le front.

## Décisions encore ouvertes

Ne pas trancher sans en discuter avec le développeur :
- GLPI ou Zammad
- Liste définitive des catégories, niveaux d'urgence et équipes (conditionne la labellisation)
- Répartition du corpus : généré / traduit / écrit à la main
- Volume cible de l'historique Parquet
- Hébergeur de pré-production
- Ergonomie et design du front (à débattre ensemble, le développeur débute en React)

## Organisation du travail

- **Rôles** : Opus planifie, découpe en **Issues GitHub** (critères d'acceptation + compétence visée), relit les PR et tient la doc à jour. Sonnet code une Issue par branche et ouvre une PR. Le développeur décide et **lit chaque PR avant fusion** : il doit pouvoir la défendre seul devant le jury.
- **Pilotage agile** : GitHub Projects (backlog, kanban, burndown). Ces traces servent de preuves pour C16.
- **Veille** : hebdomadaire, tracée dans `docs/veille/`.
- **Petits pas** : une fonctionnalité à la fois, testée, commitée. Pas de gros refactor non demandé.
- **Tests** : toute logique de données ou de modèle a ses tests pytest.
- **Sécurité** : OWASP par défaut (validation des entrées, authentification des API, pas de secrets en dur).

## Façon d'échanger

- **Langue** : échanger en français. Code, variables et noms de fichiers en anglais. Documentation (README, docs/) en français, car destinée au jury.
- **Pédagogie** : expliquer brièvement *pourquoi* chaque choix et mentionner l'alternative écartée. Préférer un code simple et lisible à un code astucieux. Expliquer davantage tout ce qui touche au front.

## Journal de projet

`JOURNAL.md` sert de matière première aux rapports (pilotage, choix techniques, incident E5). **Quand une décision est prise ou un bug significatif résolu, proposer une entrée** :

```
## AAAA-MM-JJ — Titre court
**Type** : décision | bug | incident
**Contexte** : …
**Choix / Cause** : …
**Raison / Résolution** : …
```

Les bugs sont documentés avec symptôme, logs pertinents et résolution : l'un d'eux servira d'incident E5.

## Routage

Ne charger que ce qui sert la tâche en cours, pour préserver le contexte.

| Tâche | Où regarder |
|---|---|
| Planifier une Issue ou contrôler une PR / un livrable | Skill **`referentiel`** (`.claude/skills/referentiel/`) : ne charger que le bloc E1–E5 concerné |
| Formulation exacte d'un critère | `referentiel/*.pdf` (local, non versionné ; lisible avec `pdftotext -layout`) |
| Historique des décisions | `JOURNAL.md` |
| Cours de la formation | Dossiers indiqués par le développeur au cas par cas |

**Règle** : toute Issue créée passe par la skill `referentiel` (mode planification), et toute PR est relue avec elle (mode contrôle).

Autres skills (RGPD, front accessible, MLOps…), plugins et serveurs MCP : **à définir ensemble**, puis à référencer ici.

## Priorités actuelles

1. ~~Structure du dépôt, `.gitignore`, `.env.example`, `README.md`, `JOURNAL.md`~~ (fait)
2. Pilotage : GitHub Projects + Issues du backlog initial
3. Veille : outil d'agrégation (RSS), sources qualifiées, gabarit de synthèse accessible, premier créneau hebdomadaire
4. Preuve de concept Groq : appel simple, mesure de latence, gestion des quotas, bascule vers Ollama
5. Déploiement de l'outil de ticketing en Docker (après choix GLPI / Zammad)
6. Définition des catégories, puis générateur de tickets synthétiques

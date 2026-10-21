# CLAUDE.md — Triage IA des tickets et alertes MSP

Contexte permanent du projet. Ce fichier reste **court** : les détails par domaine se chargent à la demande (voir « Routage »). Le mettre à jour dès qu'une décision est prise.

## Contexte

Projet de fin de formation **Développeur en intelligence artificielle (Simplon)**. Soutenance devant jury en **juillet 2027** ; objectif : projet **terminé début 2027**, puis peaufinage et répétitions. Le développeur est en reconversion, travaille dans un MSP (Autotask, Zabbix, Rewst) et est **débutant en front-end**. Rythme : 2 à 3 h par semaine minimum, plus quand possible.

**Commanditaire fictif** : un MSP d'une trentaine de personnes gérant une soixantaine de PME clientes.

**Problème** : des centaines de tickets et d'alertes par jour dans une file unique ; tri manuel (catégorie, urgence, équipe, cas similaires), lent et source d'erreurs de routage.

**Solution** : pour chaque ticket entrant, l'application
1. le **classe** (catégorie, urgence, équipe) via un modèle entraîné dans le projet ;
2. **suggère une piste de résolution** via un LLM, à partir des tickets résolus et de la documentation ;
3. **apprend de ce que font déjà les techniciens** (exceptions traitées, revues de priorité, corrections après coup → ré-entraînement).

**Principe** : aucune action sur les systèmes des clients (pas de remédiation automatique, pas de réponse automatique au client). Les tickets sont créés et classés automatiquement quand la confiance est suffisante ; les cas incertains (file d'exceptions) et les hausses de priorité (revue de priorité) sont toujours soumis à un humain. Règles pour les alertes de supervision structurées, modèle pour le texte libre : voir `docs/conception-tri.md`.

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

**Modèles de décision (« Jev-like »)** (Jev de TypeSafe AI, Clef de Cloudflare, pplx-decider de Perplexity, Kev en open source ; pris en charge par Ollama depuis septembre 2026, voir la veille du 2026-10-21 et #30) : classifieurs peu verbeux, bon marché sur gros volume, qui renvoient des scores de confiance. Uniquement **comparateurs dans le benchmark** et sujet de veille, jamais en remplacement du classifieur maison.

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

**Documentation** : OpenAPI généré par FastAPI pour les API ; **MkDocs + Material** pour la doc projet, publiée sur GitHub Pages par la CI (https://timdazayous.github.io/Projet_Simplon_FIN_ETUDES/). Toute nouvelle page de `docs/` doit être ajoutée à la `nav` de `mkdocs.yml`. Material atteint sa **fin de vie le 5 novembre 2026** (annoncé dans la 9.7.7) : essai de Zensical suivi dans #13 (sprint 3). Sphinx écarté (plus lourd).

**Outil de ticketing** : **GLPI 11.0.11** en Docker (`infra/glpi/`, tags épinglés `glpi/glpi:11.0.11` et `mariadb:10.11.19`, ports locaux 8082 et 3307, procédure dans `docs/glpi.md`). GLPI 12 sorti le 2026-10-18 : réévaluation suivie dans #24. Il fournit les sources API REST (API v2, OAuth2) et SQL direct. Zammad écarté (Elasticsearch, 4 Go de RAM minimum, orientation support client). Voir `docs/decisions/outil-ticketing.md`.

**Taxonomie** : 12 catégories, 3 types (incident, demande de service, information), 4 priorités, 6 équipes déduites par règles de routage. Référence unique : `config/taxonomy.yaml` ; docs : `docs/taxonomie.md`, `docs/conception-tri.md`.

**Corpus** : ~6 000 messages d'entraînement (60 % publics traduits, 40 % générés), test externe ~650 tickets réels tasksource traduits, 50 tickets relus par le développeur, ~1 500 alertes générées. Traduction OPUS-MT sur CPU. Aucun jeu de données dans le dépôt. Plan B ponctuel : Kaggle / Colab (données publiques, notebook versionné), jamais pour le modèle livré. Voir `docs/donnees/jeux-publics.md`.

**Stack** : Python 3.12 (uv), FastAPI, PostgreSQL + pgvector, PySpark / Spark SQL sur Parquet (dans Docker), DVC, MLflow, Evidently, pytest, GitHub Actions, Prometheus + Grafana, Loki, **React** pour le front.

## Décisions encore ouvertes

Ne pas trancher sans en discuter avec le développeur :
- Seuil de confiance de l'automatisation (à fixer après l'évaluation du modèle) ; niveaux de gravité Meraki à compléter
- Volume cible de l'historique Parquet
- Hébergeur de pré-production
- Ergonomie et design du front (à débattre ensemble, le développeur débute en React)

## Organisation du travail

- **Rôles** : Opus planifie, découpe en **Issues GitHub** (critères d'acceptation + compétence visée), relit les PR et tient la doc à jour. Sonnet code une Issue par branche et ouvre une PR. Le développeur décide et **lit chaque PR avant fusion** : il doit pouvoir la défendre seul devant le jury.
- **GitHub** : Opus gère les relectures (commentaire de contrôle référentiel sur la PR), la fusion (après le « ok » du développeur), le Project et la fermeture des Issues. Chaque PR contient `Closes #N`.
- **Agents Sonnet** : Opus les lance lui-même (outil Agent, `model: sonnet`, `isolation: worktree`), sur demande du développeur, une Issue par agent. Ils travaillent toujours dans un worktree, jamais dans le dossier principal. Le prompt rappelle : lire CLAUDE.md, traiter l'Issue #N, tests verts, PR avec `Closes #N`.
- **Pilotage agile** : GitHub Projects (backlog, kanban, burn-up). Ces traces servent de preuves pour C16.
- **Veille** : 1 h par semaine le week-end, agrégateur FreshRSS (`tools/freshrss/`, sources dans `docs/veille/sources.opml`), synthèses dans `docs/veille/AAAA-MM-JJ.md` à ajouter à la nav. Une information qui impose une action devient une Issue.
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

## Mémo oral

Dépôt privé séparé `timdazayous/memo-oral-simplon`, cloné dans `../memo-oral-simplon/`. Il contient des fiches question / réponse / alternative écartée / où regarder, classées par thème. **Opus l'alimente à chaque décision et à chaque PR relue**, y compris pour les petits choix (options de configuration, détails de sécurité…). Le JOURNAL garde les décisions pour le rapport ; le mémo garde tous les détails pour l'oral.

## Routage

Ne charger que ce qui sert la tâche en cours, pour préserver le contexte.

| Tâche | Où regarder |
|---|---|
| Planifier une Issue ou contrôler une PR / un livrable | Skill **`referentiel`** (`.claude/skills/referentiel/`) : ne charger que le bloc E1–E5 concerné |
| Formulation exacte d'un critère | `referentiel/*.pdf` (local, non versionné ; lisible avec `pdftotext -layout`) |
| Historique des décisions | `JOURNAL.md` |
| Cours et TP de la formation | Dossiers frères dans `../` (ex. `docker-compose-prometheus-grafana`, `loki`, `uptime_kuma_init`, `EvidentlyAI_Tuto_Kim`, `TUTO_PG_VECTOR`, `Tuto_PySpark`, `TUTO_SELENIUM`, `Securite_JWT`, `SPHINX_INIT`, `Projet_AGILE`, `Projet_3_0_Prefect_MLFactory`, `HashicorpVault`, `tuto-traefik`) : lire seulement celui qui concerne la tâche, et préférer les outils déjà vus en formation à confort égal |

**Règle** : toute Issue créée passe par la skill `referentiel` (mode planification), et toute PR est relue avec elle (mode contrôle).

Autres skills (RGPD, front accessible, MLOps…), plugins et serveurs MCP : **à définir ensemble**, puis à référencer ici.

## Priorités actuelles

Le backlog fait foi : **GitHub Project « Triage IA MSP — Pilotage »** (https://github.com/users/timdazayous/projects/2, public). Sprints de 2 semaines depuis le 2026-10-06. Jalons : « Phase 1 — Cadrage et fondations » (→ 2026-11-02), « Phase 2 — Données (E1) » (→ 2026-12-13). **En début de séance, faire le point** avec `gh pr list`, `gh issue list` et l'état du Project plutôt que de se fier à ce résumé.

État au 2026-10-21 :
- **Sprint 1** (6 → 19 octobre) : terminé, 15 points sur 18. Compte rendu : `docs/sprints/sprint-01.md`.
- **Sprint 2** (20 octobre → 2 novembre) : **toutes les Issues terminées** (#22 GLPI en Docker, #5 cadrage, #6 taxonomie et conception du tri, #27 inventaire des jeux publics, #8 première synthèse de veille). Revue et rétrospective à faire le 2 novembre dans `docs/sprints/sprint-02.md`.
- **Sprint 3** (3 → 16 novembre), Issues prêtes : #26 générateur de tickets (Sonnet), #29 récupération et traduction des jeux publics (Sonnet, mesurer la charge du poste sur un échantillon avant tout traitement en masse), #13 essai de Zensical (avant le 5 novembre).
- **Backlog** : #15 tri automatique de la veille (optionnel), #24 réévaluer GLPI 12, #30 benchmark des modèles de décision (phase 3), #31 exigences AI Act.
- **Ensuite** : extraction depuis GLPI (API et SQL), base de données Merise / RGPD, API de données.

En attente du développeur :
- **Premier démarrage de GLPI** ensemble (mots de passe par défaut à changer, mesure de la RAM ; la VM Docker est limitée à ~3,8 Go, à augmenter plus tard pour la stack complète).
- Mettre à jour Ollama (`winget upgrade Ollama.Ollama`, cible ≥ 0.40.7) et FreshRSS (`pull` puis `up -d`).
- Décider : conserver ou retirer la source FreshRSS 1.30.2 de la synthèse du 2026-10-21 (Opus recommande de la conserver).
- #31 réduite le 2026-10-21 à la mention « généré par IA » (1 point) ; formation et chaîne de valeur en point de vigilance dans `docs/cadrage.md`.
- Sprint 3 avancé le 2026-10-21 (quota) : #26 et #13 lancées en agents Sonnet ; PR #33 (essai Zensical, `Refs #13`) en relecture.

Labels : `E1-donnees` à `E5-production`, `transverse`, `pour:sonnet` (prête à coder), `pour:tim` (action ou décision du développeur), `decision`, `optionnel` (bonus abandonnable sans impact sur le référentiel).

## Aide-mémoire technique

- **Poste Windows** : `python` n'est pas dans le PATH, toujours passer par `uv run` ; les avertissements Git LF/CRLF sont sans conséquence ; les chemins trop longs du dossier temporaire peuvent bloquer une suppression.
- **GitHub Project** (pour `gh project item-edit`) : projet `PVT_kwHOAJG3HM4Bl-Zb` ; champ Status `PVTSSF_lAHOAJG3HM4Bl-ZbzhkpKRg` (Backlog `df7afd10`, À faire `85453a66`, En cours `b9e5c00b`, En revue `256d054b`, Terminé `ddb9dee6`) ; champ Sprint `PVTIF_lAHOAJG3HM4Bl-ZbzhkpKWE` (Sprint 1 `8a375d0e`, Sprint 2 `0ec3ef90`, Sprint 3 `be9d1486`) ; champ Estimation `PVTF_lAHOAJG3HM4Bl-ZbzhkpKWA`. Les workflows du Project passent les Issues fermées en « Terminé », mais vérifier.
- **Après fusion d'une PR d'agent** : `git switch main && git pull`, puis `git worktree remove .claude/worktrees/<agent>` et suppression des branches locales. Attendre la fin de la CI avant `gh pr merge` (sinon « Base branch was modified »).
- **Relecture d'une PR d'agent** : vérifier soi-même les affirmations importantes (licences, versions, reproduction d'un bug) avant de les reprendre ; poster le contrôle référentiel en commentaire ; mettre à jour JOURNAL et mémo oral après fusion.
- **Mesures sur le poste** : surveiller CPU et RAM pendant tout traitement lourd (Ollama, traduction, Spark) et arrêter si la RAM libre passe sous ~1 Go.

# CLAUDE.md — Triage IA des tickets et alertes MSP

Ce fichier donne le contexte du projet à Claude Code. À lire au début de chaque session.

## Contexte

Projet de fin de formation **Développeur en intelligence artificielle (Simplon)**, présenté devant un jury de certification. Le développeur est en reconversion professionnelle et travaille dans un MSP (prestataire d'infogérance) qui utilise Autotask, Zabbix et Rewst. Le projet s'appuie sur cette expérience terrain avec un **commanditaire fictif** : un MSP d'une trentaine de personnes gérant une soixantaine de PME clientes.

**Problème :** un MSP reçoit des centaines de tickets et d'alertes par jour dans une file unique. Le tri (catégorie, urgence, équipe, recherche de cas similaires) est manuel, lent et source d'erreurs de routage.

**Solution :** une application qui, pour chaque ticket entrant :
1. le **classe** (catégorie, urgence, équipe destinataire) via un modèle entraîné dans le projet ;
2. **suggère une piste de résolution** via un LLM, à partir des tickets résolus et de la documentation technique ;
3. **apprend des corrections** des techniciens (boucle de feedback → ré-entraînement).

L'outil aide le technicien à décider, il n'agit jamais seul. Pas de remédiation automatique.

## Le référentiel pilote les choix

Chaque brique existe parce qu'une compétence l'exige. Ne pas simplifier une brique sans vérifier qu'elle ne valide pas un critère.

| Bloc | Ce qu'il impose concrètement |
|---|---|
| **E1** — Données | Extraction depuis **5 types de sources** (API REST, BDD SQL, fichier, scraping, big data). Requêtes SQL documentées. Agrégation et nettoyage. Modélisation Merise + BDD conforme RGPD. API REST de mise à disposition des données, sécurisée. |
| **E2** — Veille et service IA | Veille hebdomadaire tracée. Benchmark de services IA (y compris écartés). Installation, configuration et monitoring d'un service IA existant. |
| **E3** — Modèle | API exposant le modèle (sécurisée, testée). Monitoring du modèle. **Tests automatisés sur données, entraînement et évaluation.** **Chaîne CI qui ré-entraîne et évalue le modèle.** |
| **E4** — Application | User stories, méthode agile, accessibilité (RGAA/WCAG), OWASP Top 10, tests, CI/CD. |
| **E5** — Production | Monitoring de l'application, journalisation, **résolution documentée d'un incident réel**. |

## Contraintes dures

- **Zéro budget** : outils gratuits ou open source uniquement.
- **Pas de GPU**, ni en local ni en CI. Tout entraînement doit tenir sur CPU dans un runner GitHub Actions gratuit (durée limitée par job).
- **Langue** : les tickets et l'interface sont en **français**.
- **RGPD** : les tickets contiennent des données personnelles (noms, e-mails, IP, parfois identifiants collés en clair). Elles sont **pseudonymisées avant tout traitement**, et impérativement **avant tout envoi à un service externe** (Groq). Ne jamais logger de contenu de ticket brut.
- **Secrets** : uniquement dans `.env` (ignoré par Git). Maintenir un `.env.example` à jour sans valeurs réelles.

## Choix techniques actés

**Deux briques IA distinctes — ne pas les fusionner :**

- **Classifieur entraîné dans le projet** : baseline TF-IDF + régression logistique (scikit-learn), puis CamemBERT distillé si le gain est démontré. C'est ce modèle que la CI ré-entraîne. Il est central pour E3 : il ne doit jamais être remplacé par un service externe.
- **Service LLM existant** pour résumé et suggestion : **Groq** (free tier) en principal, **Ollama** en local en secours. Les deux exposent une API compatible OpenAI : le code passe par une seule abstraction et le fournisseur se choisit par variable d'environnement (ex. `LLM_PROVIDER=groq|ollama`). Gérer explicitement les erreurs 429 (quotas Groq) avec retry/backoff et repli possible sur Ollama.

**Modèles de décision (type Jev : modèles Ollama nimble/tev1, Cloudflare Clef)** : uniquement comme **comparateurs dans le benchmark**, face au classifieur maison. Ne pas les utiliser pour remplacer le classifieur.

**Stack envisagée :**
- Python, FastAPI, PostgreSQL (+ pgvector pour la recherche sémantique)
- PySpark sur Parquet partitionné pour la source big data
- DVC (données/modèles), MLflow (expérimentations), Evidently (dérive)
- pytest, GitHub Actions
- Prometheus + Grafana, Loki (logs)
- Front : à définir (React probable), accessibilité RGAA obligatoire

## Sources de données

| Type | Source | Rôle |
|---|---|---|
| API REST | Outil de ticketing open source en Docker (GLPI ou Zammad) simulant le SI du MSP | Tickets courants |
| BDD | Base de ce même outil, interrogée en SQL direct | Historique, agrégats |
| Fichier | Datasets publics de tickets support (Kaggle, Bitext…) | Enrichir le corpus |
| Scraping | Microsoft Learn, forums techniques (respect robots.txt et CGU, temporisation) | Base de connaissances |
| Big data | Historique et logs volumineux en Parquet, traités en PySpark | Volume, suivi du modèle |

**Corpus** : tickets synthétiques réalistes générés à partir de l'expérience MSP du développeur, injectés dans l'outil de ticketing. Garder un jeu de test écrit différemment (datasets publics traduits ou tickets reformulés) pour éviter que le modèle n'apprenne seulement le style du générateur.

## Décisions encore ouvertes

Ne pas trancher ces points sans en discuter avec le développeur :
- GLPI ou Zammad
- Liste définitive des catégories, niveaux d'urgence et équipes (conditionne toute la labellisation)
- Répartition du corpus : généré / traduit / écrit à la main
- Volume cible de l'historique Parquet

## Façon de travailler

- **Langue** : échanger en français. Code, noms de variables et de fichiers en anglais. Documentation du projet (README, docs/) en français, car destinée au jury.
- **Pédagogie** : le développeur doit pouvoir défendre chaque choix devant le jury. Quand tu proposes une solution, explique brièvement *pourquoi* et mentionne l'alternative écartée. Préfère un code simple et lisible à un code astucieux.
- **Petits pas** : une fonctionnalité à la fois, testée, commitée. Pas de gros refactor non demandé.
- **Tests** : toute logique de données ou de modèle est accompagnée de tests pytest.
- **Sécurité** : penser OWASP par défaut (validation des entrées, authentification des API, pas de secrets en dur).

## Journal de projet

Le fichier `JOURNAL.md` à la racine sert de matière première au rapport de certification (pilotage agile, choix techniques, incident E5). **Quand une décision technique est prise ou un bug significatif est résolu, propose une entrée à ajouter**, au format :

```
## AAAA-MM-JJ — Titre court
**Type** : décision | bug | incident
**Contexte** : …
**Choix / Cause** : …
**Raison / Résolution** : …
```

Les bugs doivent être documentés avec symptôme, logs pertinents et résolution : l'un d'eux servira d'incident documenté pour E5.

## Priorités actuelles

1. Structure du dépôt, `.gitignore`, `.env.example`, `README.md`, `JOURNAL.md`
2. Preuve de concept Groq : appel simple, mesure de latence, gestion des quotas, bascule vers Ollama
3. Déploiement de l'outil de ticketing en Docker (après choix GLPI / Zammad)
4. Définition des catégories, puis générateur de tickets synthétiques

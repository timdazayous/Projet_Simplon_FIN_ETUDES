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

## 2026-10-10 — Volume de la veille et aide au tri optionnelle
**Type** : décision
**Contexte** : dès la première séance, le volume d'articles remontés par FreshRSS dépasse ce qu'une heure permet de trier : les archives sont importées au premier abonnement, et certaines sources sont très prolifiques (CERT-FR couvre tous les logiciels ; le flux complet de Simon Willison publie environ 40 billets par semaine).
**Choix / Cause** : réduire le volume avec les fonctions natives de FreshRSS (archives de plus de 7 jours marquées comme lues, filtre d'action sur CERT-FR limité aux composants du projet, flux « articles de fond » pour Simon Willison) ; annoter les articles pendant les séances (favori = pertinent). Ajout au backlog d'une aide au tri par classifieur (Issue #15), explicitement **optionnelle**.
**Raison / Résolution** : les filtres natifs suffisent à rendre la veille tenable, donc C6 ne dépend pas du classifieur. L'aide au tri est retenue comme bonus parce qu'elle répond à un besoin réel, réutilise la démarche du projet (annotation humaine, classifieur, évaluation) et fournit un cas mesuré au benchmark (C7). Si le temps manque, elle est abandonnée sans impact sur le référentiel.

## 2026-10-10 — Première mesure réelle du service LLM
**Type** : décision
**Contexte** : après la fusion du client LLM (#4, PR #18), mesure réelle de Groq et d'Ollama sur le poste de développement, avec relevé du processeur et de la mémoire toutes les 2 secondes.
**Choix / Cause** : Groq (`openai/gpt-oss-20b`) confirmé comme fournisseur principal : 739 ms en moyenne sur 6 appels, aucun échec, charge négligeable sur le poste. Modèle de secours Ollama : `gemma3:4b` (13 s par réponse une fois chargé) à la place de `qwen3:4b`, qui dépasse le délai de 60 s sur CPU. Le repli reste désactivé par défaut.
**Raison / Résolution** : `qwen3:4b` est un modèle à raisonnement, trop lent sur CPU, et sa charge a fait tomber la RAM libre à 826 Mo. `gemma3:4b`, sans raisonnement, répond dans le délai avec une charge acceptable. Détails dans `docs/service-llm.md`, section « Résultats de mesure ».

## 2026-10-10 — Délai dépassé réessayé six fois avec Ollama
**Type** : bug
**Contexte** : pendant la mesure, `scripts/llm_poc.py 3 --provider ollama` avec `qwen3:4b` n'a pas terminé en plus de 10 minutes.
**Choix / Cause** : symptôme reproduit avec un seul appel et sans nouvelle tentative : `error=APITimeoutError` au bout de 62 s. Le client classe le délai dépassé parmi les erreurs transitoires : il le réessaie jusqu'à 6 fois, avec backoff, soit environ 7 minutes de blocage par appel.
**Raison / Résolution** : en cours, suivi dans l'Issue #19 (pistes : ne pas réessayer un délai dépassé comme une erreur 429, délai configurable par fournisseur, test dédié). Contournement immédiat : modèle de secours `gemma3:4b`. Candidat à l'incident documenté de l'épreuve E5.

## 2026-10-19 — Résolution du bug #19 (délai dépassé)
**Type** : bug
**Contexte** : suite de l'entrée du 2026-10-10. Le client LLM réessayait un délai dépassé jusqu'à 6 fois, ce qui bloquait un appel à Ollama environ 7 minutes.
**Choix / Cause** : bug reproduit par un test (commit `3922c61` : 2 tests en échec sur le code d'origine, vérifiés en relecture), puis corrigé : `APITimeoutError` est intercepté avant les erreurs réessayées et passe directement au repli ; délai configurable par fournisseur (`GROQ_TIMEOUT_SECONDS=30`, `OLLAMA_TIMEOUT_SECONDS=120`). Les erreurs 429, 5xx et de connexion gardent le retry avec backoff.
**Raison / Résolution** : un modèle trop lent restera trop lent, donc réessayer ne fait que multiplier l'attente. Un délai par fournisseur reflète des temps de réponse très différents (moins d'une seconde pour Groq, plus de 10 s pour un modèle local sur CPU). Validation : 40 tests verts, couverture de `src/llm` à 100 %, CI verte. Correction livrée par la PR #21, incident documenté dans `docs/incidents/2026-10-10-delai-depasse-ollama.md`.

## 2026-10-19 — GLPI 11.0.11 plutôt que GLPI 12
**Type** : décision
**Contexte** : pendant le développement du déploiement Docker de GLPI (#22, PR #23), l'agent a constaté que l'image `glpi/glpi:latest` pointait déjà sur GLPI 12.0.0, publié le 2026-10-18. Vérifié en relecture sur Docker Hub : la version 11.0.11 a été publiée le même jour, la branche 11 reste donc maintenue.
**Choix / Cause** : rester sur **GLPI 11.0.11**, avec un tag d'image épinglé (`glpi/glpi:11.0.11`, `mariadb:10.11.19`) plutôt que `latest`. Réévaluation de la 12 suivie dans l'Issue #24.
**Raison / Résolution** : une version x.0.0 publiée la veille présente le plus de risques de régression ; la documentation de l'API v2 et les retours de la communauté portent sur la 11 ; épingler les tags garantit que l'installation reste reproductible (C4) même quand `latest` change. Alternative écartée : GLPI 12.0.0, à réévaluer après une ou deux versions correctives grâce à la veille.

## 2026-10-20 — Note de cadrage validée
**Type** : décision
**Contexte** : C1 attend une présentation complète du projet (acteurs, objectifs, environnements et contraintes, budget, organisation, planification) et C14 un besoin formulé de façon vérifiable.
**Choix / Cause** : note de cadrage rédigée par l'assistant et validée par le développeur (`docs/cadrage.md`) : volumétrie estimée à 250-450 tickets et alertes par jour, cinq indicateurs chiffrés (cibles provisoires, à confirmer après la baseline), budget réel nul et estimation de production à partir des tokens mesurés, cinq risques, feuille de route en cinq phases (fonctionnalités terminées vers la fin du premier trimestre 2027, finitions et répétitions d'avril à juin).
**Raison / Résolution** : la volumétrie a été validée à partir de l'expérience terrain du développeur en MSP. La feuille de route privilégie un calendrier réaliste plutôt qu'optimiste : elle est revue à chaque fin de sprint, selon la vélocité mesurée.

## 2026-10-20 — Taxonomie et conception du tri
**Type** : décision
**Contexte** : la taxonomie conditionne la labellisation, le générateur de données et le classifieur. En la discutant, une question de conception est apparue : tout confier au modèle, ou mieux concevoir l'amont (canaux d'entrée, règles) pour lui simplifier le travail.
**Choix / Cause** : combiner règles et modèle. Le canal d'entrée est une information connue à l'arrivée (jamais prédite) et sert d'indice au modèle. Les alertes de supervision, structurées, sont classées par règles (type de contrôle → catégorie, gravité harmonisée par outil → priorité). Le modèle traite le texte libre et prédit trois étiquettes : catégorie (12, dont `procurement` et `admin_billing` ajoutées), type (incident, demande de service, demande d'information) et priorité (P1 à P4). L'équipe (6, dont commandes et gestion de compte) est déduite par des règles de routage ordonnées. Référence unique : `config/taxonomy.yaml`.
**Raison / Résolution** : le modèle n'est utilisé que là où il apporte de la valeur (texte libre, clients qui se trompent de canal), ce qui le rend plus facile à bien entraîner sur CPU et réduit la consommation. Les règles sont fiables et explicables pour les alertes structurées. Les demandes d'information sont un type, pas une catégorie. Les équipes reprennent l'organisation réelle d'un MSP, selon l'expérience du développeur. Alternatives écartées : tout confier au modèle (il devinerait ce que l'on sait déjà) ; multiplier les files d'entrée sans modèle (les clients se trompent de canal).

## 2026-10-20 — Automatisation du tri et intervention humaine ciblée
**Type** : décision
**Contexte** : la première version de la conception du tri prévoyait que le technicien valide chaque proposition. Le développeur a décrit le workflow réellement en place dans le MSP qu'il connaît : création automatique des tickets quand les informations sont complètes, mails non reconnus laissés aux techniciens, mails liés à un ticket ajoutés en note, revue humaine des hausses de priorité, canal dédié aux urgences. Sa limite : reposant uniquement sur des règles, il laisse une partie des mails clients non traités.
**Choix / Cause** : le système crée et classe automatiquement les tickets quand la confiance est suffisante (règle de supervision ou modèle au-dessus d'un seuil). Les cas incertains vont dans une file d'exceptions, avec une proposition pré-remplie ; les hausses de priorité passent en revue humaine ; les tickets P1 sont notifiés dans un canal dédié. L'apprentissage exploite ce que font déjà les techniciens (exceptions traitées, décisions de revue, corrections après coup dans l'outil de ticketing), sans saisie supplémentaire. Le principe « l'outil n'agit jamais seul » devient : aucune action sur les systèmes des clients ni réponse automatique, création de tickets automatisée quand c'est sûr.
**Raison / Résolution** : l'objectif du commanditaire est de réduire le traitement manuel ; une validation systématique irait à l'encontre de cet objectif. La couche d'IA étend le workflow existant à base de règles au texte libre qu'il ne sait pas traiter. Nouvel indicateur : taux d'automatisation (cible provisoire ≥ 70 %), à la place du temps de tri.

## 2026-10-20 — Règle de routage des incidents critiques
**Type** : décision
**Contexte** : la règle de routage n°4 envoie tout incident P1 (hors sécurité, commandes et administratif) à l'équipe Systèmes et réseau, y compris un incident critique sur la messagerie, qui relèverait sinon de Cloud et collaboration.
**Choix / Cause** : règle conservée telle quelle.
**Raison / Résolution** : les incidents P1 sont rares et demandent le niveau d'expertise le plus élevé ; distinguer les cas selon le service concerné ajouterait de la complexité pour un cas marginal. La règle sera affinée si les corrections des techniciens montrent qu'elle se trompe souvent.

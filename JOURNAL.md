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

## 2026-10-20 — Corpus fondé sur des données publiques
**Type** : décision
**Contexte** : pour éviter que le modèle apprenne le style du générateur, le jeu de test doit être rédigé différemment des données d'entraînement. Rédiger 50 à 100 tickets à la main coûterait trop de temps au développeur, déjà pris par la veille.
**Choix / Cause** : base principale du corpus constituée de jeux de données publics, traduits en français si nécessaire ; générateur aligné sur leur format, qui comble les manques (alertes de supervision, administratif, mauvais canal, messages liés à un ticket, données personnelles fictives). Le développeur relit les étiquettes d'environ 50 tickets du jeu de test au lieu de les rédiger. Proportions par défaut du générateur validées. Inventaire des jeux publics préalable (#27).
**Raison / Résolution** : des textes écrits par de vraies personnes donnent des formulations plus naturelles ; relire une étiquette est bien plus rapide que rédiger un ticket, tout en gardant un regard métier sur le jeu de test. La traduction devient une étape d'homogénéisation des données (C3). Répartition précise à fixer après l'inventaire.

## 2026-10-20 — Répartition du corpus après l'inventaire des jeux publics
**Type** : décision
**Contexte** : l'inventaire (#27, `docs/donnees/jeux-publics.md`) n'a trouvé aucun jeu ouvert en français. Licences vérifiées en relecture sur Hugging Face. La base la plus volumineuse (Tobi-Bueck, CC BY-NC 4.0) est elle-même synthétique ; seul tasksource (CC BY 4.0, 2 229 tickets) contient de vrais tickets anonymisés. Cela nuance l'entrée précédente : le gain de « textes rédigés par de vraies personnes » vient surtout du jeu de test.
**Choix / Cause** : entraînement et validation sur environ 6 000 messages en texte libre (60 % publics traduits, principalement Tobi-Bueck ; 40 % générés) ; test externe sur environ 650 tickets tasksource traduits ; 50 tickets de référence relus par le développeur ; environ 1 500 alertes de supervision entièrement générées. Traduction en masse avec OPUS-MT (Apache-2.0, sur CPU) ; Groq réservé aux tickets relus. Aucun jeu de données versionné dans le dépôt public, seulement d'éventuels extraits traduits avec attribution. Plan B : traitements ponctuels lourds (traduction en masse, essai de CamemBERT) sur Kaggle ou Google Colab (offres gratuites), avec notebook versionné et uniquement des données publiques.
**Raison / Résolution** : le jeu de test composé de vrais tickets, rédigés autrement que les données d'entraînement, permet de vérifier que le modèle n'a pas seulement appris un style. La licence non commerciale de la base principale convient à un projet de démonstration : un déploiement réel exigerait un ré-entraînement sur des données utilisables commercialement (tickets du MSP, jeux sous licence ouverte). Le modèle livré reste entraînable sur CPU, car la CI doit le ré-entraîner (C13) : les GPU des plateformes en ligne ne servent qu'au plan B.

## 2026-10-21 — Périmètre des exigences de l'AI Act
**Type** : décision
**Contexte** : la première synthèse de veille a relevé deux articles de l'AI Act utiles au projet : l'article 50 (transparence : signaler un contenu généré par IA) et l'article 4 (maîtrise de l'IA : former les utilisateurs). L'Issue #31 prévoyait de les traiter tous les deux, avec une documentation de formation et le positionnement du projet dans la chaîne de valeur.
**Choix / Cause** : l'Issue #31 est réduite à la mention « généré par IA » sur chaque suggestion, critère d'acceptation de l'interface (1 point). La formation des techniciens et le positionnement dans la chaîne de valeur deviennent un point de vigilance du cadrage (section « Risques »), à évoquer à l'oral.
**Raison / Résolution** : la mention est une exigence concrète, testable et peu coûteuse, qui renforce aussi l'accessibilité de l'interface. Une formation n'a de sens qu'en cas de déploiement réel, hors du périmètre du projet ; la documenter comme vigilance montre que l'obligation est connue sans consommer du temps de développement.

## 2026-10-21 — Migration de la documentation vers Zensical
**Type** : décision
**Contexte** : Material for MkDocs, thème du site de documentation, atteint sa fin de vie le 5 novembre 2026 (note de version 9.7.7). Son successeur Zensical (même équipe, licence MIT) est en version 0.0.71, classée alpha. Un essai sur une copie du site (PR #33, résultats reproduits en relecture) montre qu'il lit le `mkdocs.yml` existant sans modification : build strict sans erreur, mêmes 19 pages, `lang="fr"`, lien d'évitement présent, build environ deux fois plus rapide et site deux fois plus léger.
**Choix / Cause** : migrer après le 5 novembre, avec la variante `classic` pour conserver l'apparence, après un contrôle d'accessibilité dans un navigateur (contraste, clavier, recherche en français). Repli : Material for MkDocs épinglé si la migration n'apporte pas de bénéfice suffisant.
**Raison / Résolution** : rester sur un outil sans maintenance finit par coûter plus cher, notamment en sécurité (la 9.7.7 corrigeait une faille XSS de la recherche). Le risque de l'alpha est limité : le site est petit, sans plugin autre que la recherche, la version sera épinglée et le retour en arrière ne demande que de changer la commande de build. Alternative écartée : rester sur Material sans échéance.

## 2026-10-21 — Générateur de tickets et d'alertes synthétiques
**Type** : décision
**Contexte** : le corpus prévoit environ 2 400 messages en texte libre générés et 1 500 alertes de supervision (#26, PR #34). Le générateur doit respecter la taxonomie, les proportions validées le 2026-10-20 et produire des données personnelles fictives pour tester la pseudonymisation.
**Choix / Cause** : générateur hors ligne à base de modèles de phrases, reproductible à graine égale, paramétré par `config/generator.yaml`. Les étiquettes et les règles (routage, supervision) sont lues dans `config/taxonomy.yaml`, jamais écrites en dur. Données personnelles repérables : domaines `.test` (RFC 2606), adresses IP de documentation (RFC 5737), champs `pii` et `contains_secret` sur chaque élément. Alertes en anglais comme les vrais outils, tickets en français. Écarts assumés : P3 47 % / P4 28 % au lieu de 45 / 30 (les messages liés plus urgents ne peuvent pas être P4), catégories administratives un peu surreprésentées (affinité du canal administratif). Correction en relecture : l'alerte d'annuaire LDAP passe de `accounts` à `infrastructure`.
**Raison / Résolution** : la génération est instantanée (0,2 s, 3,3 Mo) et ne sollicite pas le poste ; les tests (110, couverture 99 %) garantissent étiquettes valides, routage cohérent, proportions et présence des cas particuliers. La reformulation par LLM est écartée pour l'instant (coût en quota, reproductibilité) ; le risque d'apprentissage du style reste couvert par le test sur des tickets réels publics.

## 2026-10-21 — Classement des alertes d'échecs de connexion
**Type** : décision
**Contexte** : en relecture du générateur, l'alerte « trop d'échecs de connexion en 10 minutes » était classée `accounts`. Elle peut signaler une attaque par force brute comme un simple compte bloqué.
**Choix / Cause** : `security` par défaut (mot-clé `failed logon` ajouté aux règles de supervision) ; le technicien la bascule en `accounts` si sa vérification écarte l'attaque. Un compte isolé verrouillé, avec peu de tentatives, reste dans `accounts`. Règle ajoutée aux cas ambigus de la taxonomie.
**Raison / Résolution** : les deux erreurs n'ont pas le même coût : manquer une attaque est bien plus grave que faire corriger une catégorie. En pratique, l'outil de supervision ne déclenche cette alerte qu'au-delà d'un seuil (par exemple 10 échecs en 10 minutes) : sous ce seuil, c'est l'utilisateur bloqué qui ouvre un ticket, classé `accounts`. Le seuil de l'outil joue donc le rôle du nombre de tentatives proposé par le développeur. Les corrections des techniciens alimenteront le ré-entraînement.

## 2026-10-23 — Jeux publics : mesure de la traduction et correspondance des étiquettes
**Type** : décision
**Contexte** : la phase 1 de #29 (PR #38) récupère et nettoie trois jeux publics (licences vérifiées à chaque lancement) et mesure la traduction OPUS-MT sur 50 tickets : environ 1 s par ticket, CPU du processus ≤ 33 %, RAM libre minimale 2,7 Go, soit environ 1 h 20 pour les 4 873 tickets retenus. Constats : 1 603 tickets Tobi-Bueck déclarés en allemand sont en anglais ; Tobi-Bueck correspond mal à un MSP (21 % sans catégorie, `security` gonflée par un tag omniprésent, plusieurs catégories presque vides) ; certains termes techniques sont mal traduits (« Annuaire actif »). En relisant les tickets tasksource, la classe « Fileservice » s'avère composée surtout de demandes de droits sur des partages, « Support general » de créations de comptes, et « EOL » ne compte que 2 tickets.
**Choix / Cause** : traduction complète en local, de nuit, faisceau 4, avec un glossaire de termes protégés. Tobi-Bueck : seuls les tickets rattachés à une catégorie sont gardés, `security` est plafonnée ; le générateur comble les manques. tasksource : accès aux partages → `accounts` ; autres Fileservice → `infrastructure` ; fin de vie d'un système → catégorie de la ressource (`infrastructure` pour un serveur), sans nouvelle catégorie ; créations de comptes et onboarding → `accounts`, téléphones → `telephony` ; seuls les tickets vraiment flous et les 64 textes de langue indécidable sont exclus.
**Raison / Résolution** : la charge mesurée rend inutile le plan B Kaggle / Colab pour ce volume. Classer selon la taxonomie existante (droits d'accès dans `accounts`, ressource concernée pour les cycles de vie) garde des règles cohérentes avec celles des alertes ; une catégorie pour deux tickets n'aurait pas assez d'exemples pour être apprise. Garder les tickets récupérables par mots-clés préserve la taille du jeu de test, composé de vrais tickets. Alternative écartée : exclure toutes les classes ambiguës (perte d'un tiers du test).

## 2026-10-23 — Évaluation des catégories absentes du test externe
**Type** : décision
**Contexte** : après étiquetage (PR #39), le test externe tasksource (457 vrais tickets) ne contient aucun ticket `printing`, `backup`, `procurement` ni `admin_billing`. Deux options : faire rédiger une douzaine de tickets par le développeur, ou évaluer ces catégories sur des tickets générés. Par ailleurs, le tirage au hasard de 3 600 tickets d'entraînement réduisait encore les catégories rares.
**Choix / Cause** : ces quatre catégories sont évaluées sur des tickets générés, et le résultat est signalé comme optimiste dans le rapport. Les 7 682 tickets d'entraînement sont tous traduits (environ 3 h, de nuit) ; la répartition est choisie après traduction.
**Raison / Résolution** : le développeur a mis en place l'automatisation du tri dans son MSP mais ne traite pas lui-même ces tickets : des tickets qu'il rédigerait ne seraient pas plus représentatifs, et présenter honnêtement un score optimiste est préférable. Traduire tout rend la décision de répartition réversible sans retraduire.

## 2026-10-23 — Rôle du service LLM : réévaluation de la priorité
**Type** : décision
**Contexte** : la note de cadrage confiait au LLM la suggestion d'une piste de résolution, à partir des tickets résolus et de la documentation. En discutant des sources de données, le développeur a précisé que le besoin réel, dans son MSP, porte plutôt sur la priorité : un client écrit au sujet d'une alerte ou d'un ticket ouvert pour dire qu'il a absolument besoin de l'équipement à une date proche, et ce signal doit faire relever la priorité.
**Choix / Cause** : le LLM réévalue la priorité d'un ticket ouvert quand un message lié du client signale une urgence, une échéance ou un impact métier ; il renvoie une réponse structurée (escalade, priorité proposée, échéance, justification) soumise à la revue de priorité, où un humain décide. En option, il produit un résumé du ticket affiché dans l'interface du projet, avec la mention « généré par IA ». La suggestion de résolution est écartée et devient une piste d'évolution.
**Raison / Résolution** : la tâche est ancrée dans un workflow réel, déjà prévue dans la conception (revue de priorité), et relève vraiment d'un modèle de langage (comparer un message à un ticket, comprendre des dates relatives et un impact métier) ; elle reste distincte du classifieur, qui classe un texte isolé. Elle est mesurable : 800 cas publics étiquetés urgent ou non (`support-urgency`) et les messages liés du générateur. Le benchmark C7 compare Groq, Ollama et les modèles de décision sur cette tâche (#30). La suggestion de résolution demanderait des tickets résolus avec leur solution, une recherche de cas similaires et une évaluation difficile, pour 2 à 3 heures de travail par semaine. Le cadrage, le service LLM, la conception du tri, le README et CLAUDE.md sont mis à jour.

## 2026-10-23 — Cinq sources de données de types distincts
**Type** : décision
**Contexte** : le référentiel (C1) exige une extraction depuis cinq types de sources. GLPI devait en fournir deux (API REST et base de données), et aucune source de scraping n'était définie.
**Choix / Cause** : fichier = jeux publics Hugging Face (réalisé) ; API REST = API publique endoflife.date (dates de fin de support, sans clé, licence MIT) ; base de données = MariaDB de GLPI en SQL direct ; scraping = avis du CERT-FR (Licence Ouverte Etalab 2.0, `robots.txt` respecté) ; big data = historique Parquet interrogé avec Spark SQL. L'API de GLPI reste utilisée pour l'injection des tickets générés. Spécifications dans `docs/donnees/specifications-extraction.md` (PR #40).
**Raison / Résolution** : chaque source apporte une information utile au tri (cycle de vie des produits, avis de sécurité, historique) et deux types d'extraction ne reposent plus sur le même outil. Le scraping est justifié car le flux RSS du CERT-FR ne contient pas les systèmes affectés ni les CVE. Alternatives écartées : l'API NVD (recoupe le CERT-FR, quotas stricts sans clé), le scraping de forums de dépannage (conditions d'utilisation, données personnelles, sans apport pour un classifieur qui a besoin de tickets étiquetés), Selenium (pages statiques, inutilement lourd).

## 2026-10-23 — Correction de la source de scraping
**Type** : décision
**Contexte** : la spécification de l'extraction prévoyait de scraper les pages HTML des avis du CERT-FR, au motif que leur contenu détaillé n'était pas disponible dans le flux RSS. En relisant la PR #44, il est apparu que le CERT-FR publie une API JSON officielle, décrite en OpenAPI, avec les systèmes affectés déjà structurés. La vérification initiale avait porté sur le flux RSS, pas sur l'existence d'une API.
**Choix / Cause** : le CERT-FR est extrait par son API JSON (deuxième source de type API REST, en complément d'endoflife.date, #42). La source de scraping devient les pages publiques « Windows release health » de Microsoft Learn (problèmes connus des mises à jour Windows, #45). La skill `referentiel` reste hors du dépôt public et est sauvegardée dans le dépôt privé du mémo.
**Raison / Résolution** : scraper une page quand une API existe n'est pas justifiable, ni techniquement (structure fragile) ni face au jury. Les problèmes connus de Windows n'ont pas d'accès structuré gratuit (l'API Microsoft Graph exige un abonnement Microsoft 365), sont utiles à un MSP (vagues de tickets après une mise à jour) et leur `robots.txt` les autorise. Les conditions d'utilisation de Microsoft Learn n'autorisent qu'un usage personnel et non commercial, sans redistribution : aucun contenu Microsoft n'est versionné, même dans les tests, et la pré-production n'affichera que titres et liens. Leçon retenue : vérifier l'existence d'une API avant de spécifier du scraping.

## 2026-10-24 — Traduction complète des jeux publics
**Type** : décision
**Contexte** : traduction des 8 939 tickets publics retenus (7 682 d'entraînement, 457 de test externe, 800 sur l'urgence) en local, de nuit, avec OPUS-MT (faisceau 4, 4 threads, glossaire de 45 termes protégés).
**Choix / Cause** : exécution terminée sans erreur en 4 h 00, soit environ 1,6 s par ticket ; CPU du processus plafonné à un tiers de la machine, RAM libre jamais sous 4,7 Go, garde-fou mémoire jamais déclenché ; une seule balise d'anonymisation non restituée.
**Raison / Résolution** : la mesure confirme qu'aucune plateforme en ligne (Kaggle, Colab) n'était nécessaire. L'extrapolation faite sur 50 tickets avait sous-estimé la durée d'environ 30 % (faisceau plus large, textes plus longs) : pour les prochains traitements lourds, l'échantillon de mesure sera tiré au hasard dans tout le volume et réglé avec les paramètres définitifs.

## 2026-10-31 — Erreur d'étiquetage de la classe « Computer-Services »
**Type** : bug
**Contexte** : symptôme repéré en préparant la relecture des 50 tickets de référence : « Impossible d'imprimer » était étiqueté `workstation`, alors que le jeu de test était réputé ne contenir aucun ticket d'impression. Une recherche par mots-clés a montré que 30 des 37 tickets `workstation` parlaient d'imprimantes.
**Choix / Cause** : la classe d'origine « Computer-Services » avait été rattachée en bloc à `workstation` d'après son nom, et marquée douteuse, sans lecture de son contenu. Elle contient presque uniquement des demandes d'imprimantes et de copieurs (32 tickets sur 34). Une règle par mots-clés, en anglais, espagnol et portugais, les envoie maintenant en `printing` ; le reste garde `workstation`, marqué douteux.
**Raison / Résolution** : la taxonomie range l'impression dans `printing`. Le test externe contient donc 32 vrais tickets d'impression : seules `backup`, `procurement` et `admin_billing` restent évaluées sur des tickets générés. En contrepartie, `workstation` n'a plus que 5 tickets de test : son score sera peu fiable, ce qui doit être dit dans le rapport. Aucune retraduction : les étiquettes se recalculent depuis les étiquettes d'origine. Sans cette correction, un modèle qui classe bien une imprimante aurait été compté comme faux. Leçon : lire un échantillon de chaque classe avant de la rattacher, ce que la relecture de référence vise justement à contrôler.

## 2026-10-31 — Scraping des problèmes connus de Windows
**Type** : décision
**Contexte** : la cinquième source de type scraping vise les pages publiques « Windows release health » de Microsoft Learn (#45, PR #48). Le premier passage de relecture a relevé un calcul manuel de l'heure d'été et un script qui réussissait même si toutes les pages paraissaient vides.
**Choix / Cause** : BeautifulSoup sur 7 pages, délai entre les requêtes, lecteur de `robots.txt` écrit pour le projet, car celui de la bibliothèque standard de Python ignore les motifs `*` utilisés par Microsoft. L'heure passe par `zoneinfo` (`America/Los_Angeles`). Si toutes les pages sont vides, le script échoue avec le code 4 et ne touche pas à la sortie existante.
**Raison / Résolution** : essai réel : 25 problèmes en 14 secondes (15 résolus, 10 atténués, aucun ouvert) ; 372 tests passés. Selenium est écarté, car les pages sont statiques. Limites à assumer : le libellé d'un problème ouvert est supposé, testé sur du HTML fictif uniquement (un libellé inconnu arrête le script avec un message clair), et un même problème peut figurer sur plusieurs pages, à regrouper à l'agrégation. Aucun contenu Microsoft n'est versionné.

## 2026-10-31 — Répartition du corpus d'entraînement
**Type** : décision
**Contexte** : les 7 682 tickets publics traduits sont très déséquilibrés : ils couvrent mal `messaging`, `accounts`, `printing`, `backup` et `telephony`, et pas du tout `procurement` ni `admin_billing`. Un tirage au hasard aurait reproduit ce déséquilibre (#46).
**Choix / Cause** : pour chaque catégorie, `public = min(disponible, cible)`, et le générateur comble le reste. Estimation avant assemblage : environ 2 883 messages publics et 3 118 générés, soit environ 52 % de générés, contre 40 % prévus au départ.
**Raison / Résolution** : le modèle apprend sur la répartition voulue, et une catégorie abondante n'écrase pas les autres. En contrepartie, les données générées pèsent davantage ; le test externe sur de vrais tickets reste donc l'évaluation qui compte. Alternative écartée : tout le public plus un petit complément, qui aurait fait dominer `software` et `network`. Volumes réels à reprendre après l'assemblage.

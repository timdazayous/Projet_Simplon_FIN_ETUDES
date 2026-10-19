# Note de cadrage

**Statut** : version 1 du 19 octobre 2026, à valider par le développeur · **Issue** : #5 · **Compétences** : C1 (présentation du projet), C14 (analyse du besoin)

Cette note présente le projet, son commanditaire, ses objectifs, son périmètre, ses contraintes, son budget et son organisation. Elle sert de référence pour les spécifications et pour les rapports de certification.

## Contexte

### Le commanditaire

Le commanditaire est un **prestataire de services informatiques managés** (MSP) **fictif**. Il compte une trentaine de collaborateurs et assure l'infogérance d'une soixantaine de PME clientes : support aux utilisateurs, administration des serveurs et du réseau, sécurité, sauvegarde.

Le scénario s'appuie sur l'expérience réelle du développeur, qui travaille dans un MSP utilisant des outils comparables (gestion de tickets, supervision, automatisation). Aucune donnée réelle n'est utilisée dans le projet.

### Volumétrie estimée

Ces chiffres sont des **hypothèses de travail**, utilisées pour dimensionner le projet. Ils seront affinés avec le générateur de tickets synthétiques.

| Élément | Estimation | Raisonnement |
|---|---|---|
| Utilisateurs finaux couverts | environ 1 200 | 60 PME × 20 utilisateurs en moyenne |
| Tickets créés par les utilisateurs | 100 à 150 par jour ouvré | ordre de grandeur d'un service desk de cette taille |
| Alertes de supervision | 150 à 300 par jour | serveurs, réseau, sauvegardes, sécurité |
| **Total à trier** | **250 à 450 éléments par jour** | une file unique, triée à la main |

### Le problème

Tous les tickets et toutes les alertes arrivent dans **une file unique**. Un technicien doit les lire un par un pour décider de la catégorie, de la priorité et de l'équipe à qui les confier, puis chercher si un cas similaire a déjà été résolu. Ce tri est :

- **lent** : quelques minutes par ticket, soit plusieurs heures de travail par jour à l'échelle du service ;
- **source d'erreurs** : un ticket mal routé change d'équipe une ou plusieurs fois avant d'être traité, ce qui retarde sa résolution ;
- **dépendant des personnes** : la qualité du tri varie selon l'expérience du technicien et sa connaissance des clients.

## Acteurs

| Acteur | Rôle dans le projet | Attentes |
|---|---|---|
| Direction du MSP | Commanditaire | Gagner du temps de tri, réduire les erreurs de routage, sans coût supplémentaire |
| Techniciens N1 et N2 | Utilisateurs principaux | Une proposition de classement fiable et une piste de résolution, qu'ils valident ou corrigent |
| Responsable du service desk | Utilisateur et pilote | Suivre la qualité du tri et l'évolution du modèle |
| Clients finaux (salariés des PME) | Émetteurs des tickets, bénéficiaires indirects | Être pris en charge plus vite par la bonne équipe |
| Délégué à la protection des données (DPO) | Garant du RGPD | Données personnelles minimisées, pseudonymisées, jamais envoyées en clair à un service externe |
| Équipe projet | Réalisation | Le développeur (décisions, relecture, livrables), assisté d'agents IA pour la planification et le développement |

## Objectifs

### Objectifs fonctionnels

Pour chaque ticket ou alerte entrant, l'application doit :

1. **proposer un classement** : catégorie, priorité et équipe destinataire, avec un indice de confiance ;
2. **suggérer une piste de résolution**, en s'appuyant sur les tickets déjà résolus et sur la documentation technique ;
3. **permettre au technicien de valider ou de corriger** ce classement en un minimum d'actions ;
4. **apprendre des corrections** : elles alimentent le ré-entraînement du modèle.

L'outil **aide à décider, il n'agit jamais seul** : aucune action n'est exécutée automatiquement sur les systèmes des clients.

### Objectifs techniques

- Un **classifieur entraîné dans le projet**, léger et ré-entraînable sur CPU, plutôt qu'un service externe pour le classement.
- Un **service LLM existant** (Groq, avec Ollama en secours) pour les suggestions de résolution, derrière une interface unique.
- Une **chaîne de données** reproductible : extraction depuis cinq types de sources, nettoyage, base de données conforme au RGPD, API d'accès.
- Une **chaîne MLOps** : tests des données et du modèle, ré-entraînement et évaluation automatiques, livraison par Pull Request avec rapport, monitoring et alertes.
- Une **application web accessible** (RGAA / WCAG) et sécurisée (OWASP).

### Indicateurs de réussite

Les valeurs cibles sont **provisoires** : elles seront confirmées une fois la première version du classifieur (baseline) mesurée.

| Indicateur | Mesure | Cible provisoire |
|---|---|---|
| Qualité du classement par catégorie | F1-score macro sur un jeu de test rédigé différemment des données d'entraînement | ≥ 0,80 |
| Qualité du routage | Part des tickets dont l'équipe proposée est la bonne | ≥ 85 % |
| Temps de tri | Temps entre l'ouverture du ticket par le technicien et sa validation | divisé par deux par rapport à un tri manuel simulé |
| Corrections | Part des propositions corrigées par les techniciens, suivie dans le temps | en baisse après chaque ré-entraînement |
| Disponibilité de la suggestion | Part des demandes de suggestion qui aboutissent (Groq ou secours) | ≥ 99 % |

## Périmètre

| Dans le périmètre | Hors périmètre |
|---|---|
| Classement des tickets et alertes (catégorie, priorité, équipe) | Exécution automatique d'actions correctives |
| Suggestion de piste de résolution | Réponse automatique envoyée au client |
| Interface de validation et de correction pour les techniciens | Intégration à un outil de ticketing réel en production (le projet utilise GLPI en local pour simuler le SI) |
| Ré-entraînement à partir des corrections | Données réelles de clients : tous les tickets sont synthétiques ou issus de jeux de données publics |
| Monitoring du modèle et de l'application | Application mobile |

## Environnements et contraintes

### Environnements

| Environnement | Rôle | Description |
|---|---|---|
| Développement | Poste du développeur | Windows 11, 12 cœurs, 15 Go de RAM, **sans GPU** ; Python 3.12 (uv), Docker |
| Local complet | Démonstration et procédures d'installation | Stack complète en Docker : GLPI, PostgreSQL, monitoring, Spark |
| Intégration continue | Contrôle qualité | GitHub Actions (runners gratuits, sur CPU) |
| Pré-production | Preuve de concept accessible en ligne | Hébergement gratuit allégé (API, front, base de données) ; hébergeur à choisir |

### Contraintes

| Contrainte | Conséquence sur le projet |
|---|---|
| **Budget nul** | Uniquement des outils gratuits ou open source, des offres gratuites de services en ligne |
| **Pas de GPU** | Classifieur léger (TF-IDF et régression logistique, puis CamemBERT distillé seulement si le gain le justifie) ; LLM en ligne plutôt qu'en local |
| **RGPD** | Pseudonymisation avant tout traitement et avant tout envoi à un service externe ; aucun contenu de ticket dans les logs ; registre des traitements et procédures de purge |
| **Langue française** | Tickets, interface et documentation en français ; modèles et données adaptés au français |
| **Accessibilité** | Interface conforme au RGAA ; documentation publiée dans un format accessible |
| **Éco-responsabilité** | Modèles sobres, appels au LLM limités à ce qui apporte une valeur, mesure de la charge |
| **Temps disponible** | Développeur en poste à temps plein : 2 à 3 heures par semaine minimum ; développement assisté par des agents IA |

## Budget

### Coût réel du projet : 0 €

| Poste | Solution | Coût |
|---|---|---|
| Code, suivi de projet, CI, documentation en ligne | GitHub (dépôt public, Actions, Projects, Pages) | 0 € |
| Service LLM | Groq (offre gratuite), Ollama (local) | 0 € |
| Outil de ticketing, base de données, monitoring | GLPI, PostgreSQL, Prometheus, Grafana, Loki (open source, en local) | 0 € |
| Agrégateur de veille | FreshRSS (open source, en local) | 0 € |
| Matériel | Poste personnel du développeur | déjà disponible |

### Estimation en cas de mise en production

Si le commanditaire déployait l'outil pour de bon, les postes de coût seraient les suivants. Les montants sont à chiffrer avec les grilles tarifaires en vigueur au moment du déploiement.

| Poste | Hypothèse de volume | Remarque |
|---|---|---|
| Hébergement (API, application, base, monitoring) | Un petit serveur virtuel | Ordre de grandeur : quelques dizaines d'euros par mois |
| Service LLM payant | 250 à 450 suggestions par jour × environ 400 tokens par appel (mesuré : environ 100 en entrée, 160 à 500 en sortie) = **100 000 à 180 000 tokens par jour** | Facturation au token ; un modèle sans raisonnement réduirait les tokens de sortie |
| Maintenance | Mises à jour, ré-entraînements, suivi du monitoring | Temps humain, à intégrer à l'activité du service |

## Risques

| Risque | Impact | Mesure prévue |
|---|---|---|
| Temps disponible réduit par l'activité professionnelle | Retard sur le planning | Sprints courts, tâches découpées, délégation aux agents, planning revu à chaque fin de sprint |
| Données synthétiques trop homogènes | Modèle qui apprend le style du générateur plutôt que le métier | Jeu de test rédigé différemment (jeux de données publics traduits, tickets reformulés) |
| Quotas de l'offre gratuite de Groq | Suggestions indisponibles | Gestion des erreurs 429, repli sur Ollama, monitoring des erreurs |
| Ressources limitées du poste (sans GPU, 15 Go de RAM) | Lenteur, impossibilité de tout lancer en même temps | Modèles légers, mesures de charge, services démarrés à la demande |
| Évolution des outils (fin de support, nouvelles versions) | Incompatibilités | Versions épinglées, veille hebdomadaire, Issues de réévaluation |

## Organisation et planification

L'organisation du travail (méthode agile, rôles, rituels, outils) est décrite dans la page [Pilotage](pilotage.md). Le suivi détaillé est tenu dans le [GitHub Project du projet](https://github.com/users/timdazayous/projects/2).

### Feuille de route

Le planning est **provisoire** : il est revu à chaque fin de sprint, en fonction de la vélocité réellement mesurée. L'objectif est de terminer les fonctionnalités au **début de l'année 2027**, puis de consacrer le printemps aux finitions et aux répétitions.

| Phase | Période visée | Contenu | Épreuves |
|---|---|---|---|
| 1. Cadrage et fondations | 6 octobre → 2 novembre 2026 | Pilotage, veille, CI, documentation, choix de l'outil de ticketing, service LLM, taxonomie, cadrage | E2 (veille, service IA), socle transverse |
| 2. Données | novembre → mi-décembre 2026 | Générateur de tickets, extraction des cinq sources, agrégation, base de données (Merise, RGPD), API de données | E1 |
| 3. Modèle et service IA | mi-décembre 2026 → janvier 2027 | Classifieur, API du modèle, tests, CI de ré-entraînement, monitoring, benchmark | E2, E3 |
| 4. Application | février 2027 | Spécifications, maquettes, front React accessible, intégration, CI/CD, pré-production | E4 |
| 5. Production | mars 2027 | Monitoring applicatif, journalisation, alertes, incident documenté | E5 |
| Finitions et préparation | avril → juin 2027 | Rapports, ajustements, répétitions de la soutenance | toutes |
| Soutenance | juillet 2027 | | |

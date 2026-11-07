# Sprint 2 — du 20 octobre au 2 novembre 2026

Jalon : Phase 1 — Cadrage et fondations (fin du jalon le 2 novembre).

## Planification (19 octobre 2026)

**Objectif du sprint** : figer la taxonomie des tickets, rédiger la note de cadrage, publier la première synthèse de veille et déployer GLPI en local.

**Capacité** : réduite côté développeur (projets importants en entreprise). Conformément à la rétrospective du sprint 1, chaque tâche du développeur est découpée pour tenir en une séance, et tout ce qui ne demande pas son expertise est confié aux agents.

| Issue | Titre | Points | Réalisée par |
|---|---|---|---|
| #8 | Veille : première synthèse (reportée du sprint 1) | 3 | Développeur |
| #6 | Taxonomie : catégories, priorités, équipes | 3 | Brouillon de l'assistant, décisions du développeur (5 questions, une par séance si besoin) |
| #5 | Note de cadrage du projet | 3 | Rédigée par l'assistant, relue par le développeur |
| #22 | Déployer GLPI 11 en Docker | 3 | Agent de développement ; premier démarrage avec le développeur |
| **Total** | | **12** | |

**Points à discuter pendant le sprint** : place éventuelle de comptes X (Twitter) dans les sources de veille, après la taxonomie.

## Changements en cours de sprint

| Date | Changement | Raison |
|---|---|---|
| 20 octobre 2026 | #27 « Inventaire des jeux de données publics » (2 points) ajoutée au sprint | Le développeur a choisi de bâtir le corpus surtout sur des données publiques, pour limiter la rédaction manuelle. Il faut d'abord identifier les jeux disponibles, leurs licences et leurs formats avant de lancer le générateur (#26). Tâche confiée à un agent, sans temps développeur. |
| 21 octobre 2026 | #36 « Site de documentation : ne plus charger les polices depuis Google Fonts » (1 point) ajoutée au sprint | Découvert pendant l'essai de Zensical (#13) : chaque visite du site transmettait l'adresse IP du visiteur à Google, ce qui pose un problème au regard du RGPD. Correction courte, confiée à un agent et terminée le jour même. |

**Périmètre après changements** : 15 points.

## Revue (7 novembre 2026)

La revue, prévue le 2 novembre, a eu lieu le 7 novembre, faute de temps du développeur.

**Points terminés / points planifiés** : 15 sur 15 (100 %).

**Livré** :

| Issue | Résultat |
|---|---|
| #5 | Note de cadrage validée : commanditaire, problème, solution, périmètre et risques |
| #6 | Taxonomie (12 catégories, 3 types, 4 priorités, 6 équipes) et conception du tri : règles pour les alertes, modèle pour le texte libre, humain pour les cas incertains |
| #8 | Première synthèse de veille (reportée du sprint 1), qui a fait naître trois décisions : migration de la documentation vers Zensical, modèles de décision dans le benchmark, périmètre de l'AI Act |
| #22 | Configuration de GLPI 11 en Docker, épinglée et validée par la CI |
| #27 | Inventaire des jeux de données publics de tickets, avec licences et formats |
| #36 | Site de documentation sans Google Fonts |

**Non terminé** : aucune Issue. Le **premier démarrage de GLPI** avec le développeur n'a toutefois pas eu lieu : la configuration est livrée et testée par la CI, mais n'a jamais tourné sur le poste. Il glisse depuis deux sprints, par manque de temps du développeur, et il est prévu en début de sprint 3.

**Travail du sprint 3 réalisé en avance** : 20 points, confiés aux agents pendant que le développeur avait peu de temps. Il s'agit du suivi de Zensical (#13), du générateur de tickets et d'alertes (#26), de la récupération et de la traduction des jeux publics (#29), et de trois sources de données : endoflife.date (#41), CERT-FR (#42) et le scraping de Microsoft Learn (#45).

**Faits marquants** :

- **Deux recadrages venus du métier du développeur** :
    - le LLM réévalue la priorité des tickets ouverts au lieu de suggérer une résolution ;
    - les cinq sources de données sont de types vraiment distincts, sans compter GLPI deux fois.
- **Trois erreurs repérées et corrigées avant d'avoir un effet** :
    - une source de scraping prévue alors qu'une API existait (CERT-FR) ;
    - une durée de traduction sous-estimée (3 h annoncées, 4 h réelles) ;
    - un étiquetage erroné des tickets d'imprimantes, repéré en préparant la relecture de référence.
- **Traduction complète de 8 939 tickets en local**, sur CPU, sans plateforme en ligne.

## Rétrospective (7 novembre 2026)

**Ce qui a bien marché** (développeur) :

- L'approche du projet et de son développement : le développeur reste concentré sur les étapes qui comptent le plus, et les retours de l'assistant sont pertinents et alignés avec sa vision du projet.
- La méthode des questions traitées une par une, pour la taxonomie et le cadrage. L'expérience du développeur en MSP rend les choix plus précis et plus proches de la réalité.
- La veille réduite à son objectif minimal : elle a déjà orienté plusieurs choix du projet.
- Les retours réguliers de l'assistant, y compris sur ses propres erreurs : ils rassurent, et ils évitent d'accumuler des corrections à faire plus tard.
- Les traitements lourds sur le poste, de nuit ou en journée à distance : aucun des deux n'est contraignant.
- Le rythme des PR : il y a beaucoup à relire, mais c'est le prix d'un développement automatisé au maximum par des agents, sans perdre le contrôle du projet. Le mémo oral permet de défendre seul les PR validées.

**Ce qui a freiné** (développeur) :

- Une forte charge de travail en entreprise ces dernières semaines, qui a repoussé le démarrage de GLPI.
- La veille reste longue à rendre efficace : plus de 4 heures sur le sprint, sans compter les réglages.
- Les limites matérielles du poste. Un poste plus puissant, un serveur privé ou des modèles payants hébergés donneraient de meilleures performances et simplifieraient l'entraînement. Cette contrainte reste toutefois représentative du marché actuel, et elle oblige à choisir des modèles légers.
- Inventaire des jeux publics : un travail complet et intéressant, mais qui, dans un vrai projet, se ferait avec le client et à partir de ses données.

**Constat de l'assistant** : le sprint est terminé à 100 %, et 20 points du sprint suivant ont été réalisés en avance. La planification ne reflète donc plus le rythme réel. Ce qui limite le projet n'est plus le développement, mais le temps de relecture et de décision du développeur, qui reste fixe : c'est tout le dilemme du travail assisté par IA.

**Actions pour le sprint 3** :

1. Démarrer GLPI avec le développeur en début de sprint.
2. Fixer l'ambition des sprints par le **temps de relecture** du développeur, et non par le travail des agents.
3. Livrer davantage de travail par validation : une PR peut regrouper des Issues liées. Chaque PR commence par un résumé des points à lire en priorité et s'accompagne de fiches dans le mémo oral, pour que la relecture reste faisable.
4. Avancer vers l'automatisation de la veille (#15), pour réduire les 4 heures passées sur le sprint : à prioriser lors de la planification du sprint 3.

# Pilotage du projet

Cette page décrit la méthode agile appliquée au projet, ses rôles, ses rituels et ses outils. Elle s'adresse à toutes les parties prenantes : elle explique comment suivre l'avancement et où trouver chaque information.

## Méthode : Scrum adapté à un développeur seul

Le projet suit **Scrum**, adapté au fait qu'un seul développeur le réalise, à temps partiel (2 à 3 heures par semaine minimum).

| Élément Scrum | Application dans le projet |
|---|---|
| Sprint | **2 semaines**, du mardi au lundi suivant ; premier sprint le 6 octobre 2026 |
| Product backlog | Les Issues GitHub du dépôt, rangées dans le GitHub Project |
| Sprint backlog | Les Issues affectées au sprint en cours (champ « Sprint ») |
| Incrément | Le code, la documentation et les livrables fusionnés sur `main` à la fin du sprint |
| Jalons | Une phase par grand objectif (ex. « Phase 1 — Cadrage et fondations ») |

**Méthode écartée** : Shape Up. Ses cycles de 6 semaines sont trop longs pour mesurer l'avancement avec un faible volume horaire hebdomadaire. Un sprint court permet de recaler le planning plus souvent.

## Rôles

| Rôle | Qui | Responsabilités |
|---|---|---|
| Product Owner et développeur | Tim (développeur) | Priorise le backlog, tranche les décisions, rédige les livrables qui lui reviennent, relit chaque Pull Request avant fusion |
| Planification et relecture | Assistant IA (modèle Claude Opus) | Découpe le travail en Issues avec des critères d'acceptation, relit les Pull Requests au regard du référentiel, tient la documentation, le journal et le tableau à jour |
| Développement assisté | Agents IA (modèle Claude Sonnet) | Réalisent une Issue à la fois, dans une copie de travail isolée, et ouvrent une Pull Request |
| Commanditaire | MSP fictif (une trentaine de personnes, une soixantaine de PME clientes) | Exprime le besoin ; ses attentes sont formalisées dans la note de cadrage |

Le développeur reste seul décisionnaire : aucune modification n'est fusionnée sans sa validation.

## Cycle de vie d'une tâche

1. **Création** : chaque tâche devient une Issue GitHub qui précise l'objectif, les critères d'acceptation, les compétences du référentiel visées et les preuves à conserver.
2. **Planification** : l'Issue reçoit une estimation en points et un sprint, puis passe de « Backlog » à « À faire ».
3. **Réalisation** : une branche dédiée est créée (`type/numéro-sujet`, ex. `docs/7-pilotage`) et l'Issue passe « En cours ».
4. **Revue** : une Pull Request est ouverte avec la mention `Closes #N`. La CI s'exécute. La relecture vérifie les critères d'acceptation et poste un compte rendu en commentaire. L'Issue passe « En revue ».
5. **Fusion** : après validation du développeur, la Pull Request est fusionnée, ce qui ferme l'Issue. Elle passe « Terminé ».

### Definition of Ready (une Issue est prête si…)

- l'objectif et le périmètre sont clairs ;
- les critères d'acceptation sont vérifiables ;
- les dépendances et prérequis sont identifiés ;
- l'estimation est posée.

### Definition of Done (une Issue est terminée si…)

- tous les critères d'acceptation sont remplis ;
- les tests existent pour toute logique de données ou de modèle, et la CI est verte ;
- la documentation concernée est à jour ;
- la Pull Request a été relue et fusionnée ;
- toute décision prise est consignée dans le [journal du projet](https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES/blob/main/JOURNAL.md).

## Rituels

| Rituel | Quand | Objectif | Modalités | Trace |
|---|---|---|---|---|
| Planification de sprint | Premier jour du sprint | Choisir les Issues du sprint selon la priorité et la capacité disponible | 30 minutes ; revue du backlog, estimation des nouvelles Issues, objectif du sprint en une phrase | Section « Planification » du compte rendu de sprint |
| Point d'avancement | Au début de chaque séance de travail | Savoir où en est chaque Issue et repérer les blocages | 5 minutes ; lecture du tableau et des Pull Requests ouvertes | Statuts du tableau |
| Revue de sprint | Dernier jour du sprint | Constater ce qui est livré et le comparer à l'objectif | 20 minutes ; démonstration de l'incrément, points terminés et non terminés | Section « Revue » du compte rendu de sprint |
| Rétrospective | Juste après la revue | Améliorer la façon de travailler | 15 minutes ; ce qui a bien marché, ce qui a freiné, une ou deux actions concrètes pour le sprint suivant | Section « Rétrospective » du compte rendu de sprint |
| Affinage du backlog | Pendant le sprint, au besoin | Préparer les Issues des sprints suivants | Rédaction des critères d'acceptation, découpage des tâches trop grosses | Issues mises à jour |

Les comptes rendus de sprint sont rangés dans `docs/sprints/` (un fichier par sprint).

**Adaptation au contexte** : les durées indiquées sont des repères, pas des contraintes. Le développeur travaillant seul avec un assistant IA, plusieurs rituels peuvent se tenir dans la même séance (par exemple revue, rétrospective et planification du sprint suivant à la suite). Ce qui ne change pas : chaque rituel garde son objectif et laisse une trace écrite. Le développeur, certifié en méthode agile, ajuste ce cadre au besoin, et chaque ajustement est noté dans le compte rendu du sprint.

## Outils de pilotage

### Tableau de bord : GitHub Project

Le [GitHub Project « Triage IA MSP — Pilotage »](https://github.com/users/timdazayous/projects/2) réunit tout le suivi :

- **Kanban** en cinq colonnes : Backlog, À faire, En cours, En revue, Terminé ;
- **Estimation** en points (1, 2, 3 ou 5), selon l'effort relatif et non en heures ;
- **Sprint** : itérations de 2 semaines ;
- **Jalon** : phase du projet ;
- **Labels** : épreuve visée (`E1-donnees` à `E5-production`, `transverse`), type de tâche (`decision`), et qui la réalise (`pour:tim`, `pour:sonnet`).

**Outil écarté** : Trello ou Jira. Ce sont des outils séparés du code, où les liens entre tâches, Pull Requests et CI se font à la main. GitHub Project les relie automatiquement et ne coûte rien.

### Graphiques d'avancement

Les graphiques se trouvent dans l'onglet « Insights » du Project :

- **Burn-up du sprint en cours** : il affiche dans le temps le total des points du sprint et les points terminés. Le burn-up a été préféré au burndown parce qu'il rend visibles les tâches ajoutées en cours de sprint.
- **Vélocité** : points des Issues fermées, par sprint. Elle sert à ajuster la charge des sprints suivants à la capacité réelle.
- **Charge par sprint** : points planifiés, par sprint.

### Journal du projet

Le [journal du projet](https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES/blob/main/JOURNAL.md) consigne les décisions techniques, les bugs significatifs et les incidents, avec leur contexte et leur justification.

## Communication

- **Avancement** : le tableau est à jour en continu, et chaque fin de sprint fait l'objet d'un compte rendu.
- **Imprévus et changements** : un changement de périmètre (Issue ajoutée, déplacée ou retirée d'un sprint) est noté dans le compte rendu du sprint, avec sa raison. Une décision technique est consignée dans le journal.
- **Accessibilité des informations** : le tableau, les Issues, les Pull Requests et cette documentation sont consultables en ligne par toutes les parties prenantes.

# Sprint 1 — du 6 au 19 octobre 2026

Jalon : Phase 1 — Cadrage et fondations.

## Planification (6 octobre 2026)

**Objectif du sprint** : poser les fondations du projet (intégration continue, pilotage, veille) et trancher le choix de l'outil de ticketing.

**Capacité** : environ 6 heures de travail du développeur sur deux semaines, plus le développement assisté.

| Issue | Titre | Points | Réalisée par |
|---|---|---|---|
| #1 | Chaîne d'intégration continue minimale | 2 | Agent de développement |
| #2 | Choix de l'outil de ticketing (GLPI ou Zammad) | 2 | Comparaison préparée par l'assistant, décision du développeur |
| #7 | Documenter la méthode agile et les rituels | 2 | Assistant, relecture du développeur |
| #8 | Mettre en place la veille hebdomadaire | 3 | Développeur |
| **Total** | | **9** | |

## Changements en cours de sprint

| Date | Changement | Raison |
|---|---|---|
| 7 octobre 2026 | #3 « Socle MkDocs publié sur GitHub Pages » (2 points) avancée du sprint 2 au sprint 1 | #1 et #2 ont été terminées plus tôt que prévu. #3 ne demande pas de temps au développeur, et la documentation pourra publier la veille et le pilotage dès leur rédaction. |
| 10 octobre 2026 | #4 « POC Groq : latence, quotas, bascule Ollama » (5 points) avancée du sprint 2 au sprint 1 | La clé Groq est prête et les modèles Ollama déjà installés : le développement peut être confié à un agent sans attendre. Le repli sur Ollama est rendu désactivable pour ménager les ressources du poste. |
| 10 octobre 2026 | #19 « Délai dépassé réessayé 6 fois avec Ollama » (2 points), bug ajouté au sprint | Découvert pendant la première mesure réelle du service LLM. Corrigé immédiatement, car il bloque le repli sur Ollama et constitue un candidat à l'incident documenté de l'épreuve E5. |

**Périmètre après changements** : 18 points.

## Revue (19 octobre 2026)

**Points terminés / points planifiés** : 15 sur 18 (83 %).

**Livré** :

| Issue | Résultat |
|---|---|
| #1 | Chaîne d'intégration continue (ruff, pytest, couverture) sur chaque push et chaque Pull Request |
| #2 | Outil de ticketing choisi : GLPI, après comparaison argumentée avec Zammad |
| #3 | Site de documentation MkDocs publié automatiquement sur GitHub Pages |
| #4 | Client LLM (Groq, repli Ollama désactivable), mesure réelle de latence et de charge du poste |
| #7 | Méthode agile, rituels et outils documentés |
| #19 | Bug découvert pendant la mesure (délai dépassé réessayé six fois), reproduit par un test, corrigé et documenté comme incident |

**Non terminé** : #8 « Mettre en place la veille hebdomadaire » (3 points). L'outillage est en place (FreshRSS en Docker, 14 sources qualifiées, filtres, modèle de synthèse), mais la première synthèse n'est pas encore rédigée. L'Issue est reportée au sprint 2.

**Faits marquants** : trois Issues ajoutées en cours de sprint (#3, #4, #19), chacune tracée avec sa raison ; un premier incident réel, documenté de bout en bout.

## Rétrospective (19 octobre 2026)

**Ce qui a bien marché** (développeur) : la planification du projet avec les agents IA, la manière d'aborder le développement, et la mise en place de la gestion agile avec GitHub.

**Ce qui a freiné** (développeur) :

- De gros projets à mener en entreprise ont réduit le temps disponible pour le projet.
- Le cadrage de la veille dans FreshRSS a pris du temps : le volume d'articles remontés est très élevé, et la mise en place des filtres et critères de tri est longue. Cet investissement devrait être rentabilisé par la suite.

**Constat de l'assistant** : la vélocité du sprint vient surtout du travail délégué aux agents (#3, #4, #19). Les tâches qui demandent du temps au développeur (#8) sont celles qui glissent.

**Actions pour le sprint 2** :

1. Reporter #8 et la limiter à son objectif minimal : une première synthèse rédigée, sans chercher à perfectionner le tri au préalable.
2. Garder un sprint léger en temps développeur : chaque tâche du développeur est découpée pour tenir en une séance (taxonomie : 5 questions traitées une par une ; note de cadrage : rédigée par l'assistant, relue par le développeur).
3. Continuer à confier aux agents tout ce qui ne demande pas l'expertise du développeur.

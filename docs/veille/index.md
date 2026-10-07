# Veille technique et réglementaire

La veille sert à garder le projet à jour sur les outils qu'il utilise et sur la réglementation qui l'encadre. Elle produit chaque semaine une synthèse courte, publiée sur ce site, et des recommandations lorsque le projet doit s'adapter.

## Thématiques

| Thématique | Pourquoi elle concerne le projet | Exemples de sujets suivis |
|---|---|---|
| **Services d'inférence LLM et modèles légers** | Le projet s'appuie sur Groq (free tier) et Ollama pour la suggestion de résolution, et compare son classifieur à des modèles de classification spécialisés | Quotas et modèles proposés par Groq, nouveaux modèles Ollama adaptés au CPU, modèles de classification économes |
| **Réglementation de l'IA et des données** | Les tickets contiennent des données personnelles et le projet envoie du texte à un service externe | AI Act (calendrier d'application, obligations), recommandations de la CNIL sur l'IA et le RGPD |
| **Outils du projet, sécurité et accessibilité** | Ces sujets conditionnent la fiabilité et la conformité de l'application | Vulnérabilités des composants utilisés, évolution d'uv, ruff, MkDocs / Material, GLPI ; actualité du RGAA |

## Organisation

- **Créneau** : 1 heure par semaine, *jour et heure à fixer*. Une séance manquée est rattrapée dans la semaine et signalée dans la synthèse suivante.
- **Déroulé d'une séance** :
    1. **15 minutes de tri** dans l'agrégateur : marquer les articles en rapport avec une thématique, ignorer le reste.
    2. **30 minutes de lecture et de vérification** : pour chaque information retenue, remonter à la source primaire (texte officiel, documentation, note de version) et la confirmer par une deuxième source fiable.
    3. **15 minutes de rédaction** de la synthèse à partir du [modèle](modele.md).
- **Diffusion** : la synthèse est publiée sur ce site (HTML accessible, consultable par toutes les parties prenantes). Lorsqu'une information impose une action dans le projet, une Issue est créée et citée dans la synthèse.

## Outils

### Agrégation des flux

Trois outils gratuits ont été comparés. *Choix à arrêter par le développeur.*

| Outil | Points forts | Limites |
|---|---|---|
| **Inoreader** (offre gratuite) | Aucun hébergement à gérer ; jusqu'à 150 abonnements, règles et filtres ; applications mobiles pour lire en déplacement | Service propriétaire, publicité dans l'offre gratuite |
| **FreshRSS** (open source, auto-hébergé) | Logiciel libre (AGPL), image Docker officielle, données conservées localement ; cohérent avec la stack Docker du projet | Il faut le faire tourner et le maintenir ; les articles ne sont récupérés que lorsque le service est démarré |
| **Feedly** (offre gratuite) | Très répandu, interface simple | Fonctions de tri limitées dans l'offre gratuite |

Les sources sans flux RSS (pages de changelog, actualités sans flux) sont consultées directement pendant la séance. La liste figure dans les [sources](sources.md).

### Partage des synthèses

Les synthèses sont des pages Markdown dans `docs/veille/`, publiées automatiquement sur ce site par la CI. Ce format respecte les recommandations d'accessibilité suivies pour toute la documentation : titres hiérarchisés, langue déclarée, liens explicites.

## Sources

Les sources retenues et leur évaluation sont détaillées dans la page [Sources de veille](sources.md). Le fichier [sources.opml](sources.opml) permet d'importer tous les flux d'un coup dans l'agrégateur choisi.

## Synthèses publiées

*Aucune pour l'instant.* La première synthèse sera publiée après la première séance.

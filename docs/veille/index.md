# Veille technique et réglementaire

La veille sert à garder le projet à jour sur les outils qu'il utilise et sur la réglementation qui l'encadre. Elle produit chaque semaine une synthèse courte, publiée sur ce site, et des recommandations lorsque le projet doit s'adapter.

## Thématiques

| Thématique | Pourquoi elle concerne le projet | Exemples de sujets suivis |
|---|---|---|
| **Services d'inférence LLM et modèles légers** | Le projet s'appuie sur Groq (free tier) et Ollama pour la suggestion de résolution, et compare son classifieur à des modèles de classification spécialisés | Quotas et modèles proposés par Groq, nouveaux modèles Ollama adaptés au CPU, modèles de classification économes |
| **Réglementation de l'IA et des données** | Les tickets contiennent des données personnelles et le projet envoie du texte à un service externe | AI Act (calendrier d'application, obligations), recommandations de la CNIL sur l'IA et le RGPD |
| **Outils du projet, sécurité et accessibilité** | Ces sujets conditionnent la fiabilité et la conformité de l'application | Vulnérabilités des composants utilisés, évolution d'uv, ruff, MkDocs / Material, GLPI ; actualité du RGAA |

## Organisation

- **Créneau** : 1 heure par semaine, **le week-end**, quand le développeur dispose de plus de temps libre. L'agrégateur tourne pendant le week-end pour récupérer les nouveaux articles avant la séance. Une séance manquée est rattrapée dans la semaine et signalée dans la synthèse suivante.
- **Déroulé d'une séance** :
    1. **15 minutes de tri** dans l'agrégateur : marquer les articles en rapport avec une thématique, ignorer le reste.
    2. **30 minutes de lecture et de vérification** : pour chaque information retenue, remonter à la source primaire (texte officiel, documentation, note de version) et la confirmer par une deuxième source fiable.
    3. **15 minutes de rédaction** de la synthèse à partir du [modèle](modele.md).
- **Diffusion** : la synthèse est publiée sur ce site (HTML accessible, consultable par toutes les parties prenantes). Lorsqu'une information impose une action dans le projet, une Issue est créée et citée dans la synthèse.

## Outils

### Agrégation des flux

Trois outils gratuits ont été comparés.

| Outil | Points forts | Limites |
|---|---|---|
| **Inoreader** (offre gratuite) | Aucun hébergement à gérer ; jusqu'à 150 abonnements, règles et filtres ; applications mobiles pour lire en déplacement | Service propriétaire, publicité ; d'après l'expérience du développeur, l'offre gratuite demande de rafraîchir régulièrement les flux à la main |
| **FreshRSS** (open source, auto-hébergé) | Logiciel libre (AGPL), image Docker officielle, données conservées localement ; cohérent avec la stack Docker du projet | Il faut le faire tourner et le maintenir ; les articles ne sont récupérés que lorsque le service est démarré |
| **Feedly** (offre gratuite) | Très répandu, interface simple | Fonctions de tri limitées dans l'offre gratuite |

**Choix : FreshRSS.** Il est libre et gratuit, il rafraîchit les flux automatiquement tant qu'il tourne, et il s'installe en Docker comme le reste du projet. Sa limite (récupérer les articles seulement quand il est démarré) est sans conséquence ici : il tourne pendant le week-end, avant la séance, et les flux suivis conservent leurs derniers articles d'une semaine sur l'autre.

#### Installation et utilisation de FreshRSS

La configuration est versionnée dans `tools/freshrss/docker-compose.yml`. Elle utilise l'image officielle `freshrss/freshrss`, avec une base SQLite intégrée : aucun autre service n'est nécessaire.

| Étape | Commande ou action |
|---|---|
| Démarrer (début du week-end) | `docker compose -f tools/freshrss/docker-compose.yml up -d` |
| Première configuration (une seule fois) | Ouvrir http://localhost:8081, choisir la langue française et la base SQLite, créer le compte administrateur |
| Importer les sources (une seule fois) | Dans FreshRSS : Abonnements → Importer / exporter → choisir le fichier `docs/veille/sources.opml` |
| Arrêter (fin du week-end) | `docker compose -f tools/freshrss/docker-compose.yml stop` |
| Mettre à jour FreshRSS | `docker compose -f tools/freshrss/docker-compose.yml pull`, puis la commande de démarrage |

Choix de configuration :

- **Port lié à `127.0.0.1`** : l'agrégateur n'est accessible que depuis la machine du développeur, jamais depuis le réseau.
- **Rafraîchissement automatique** aux minutes 1 et 31 de chaque heure (variable `CRON_MIN`).
- **Volumes Docker nommés** : la configuration, le compte et les articles lus sont conservés entre deux week-ends.
- **Taille des journaux limitée** à 10 Mo.

Les sources sans flux RSS (pages de changelog, actualités sans flux) sont consultées directement pendant la séance. La liste figure dans les [sources](sources.md).

### Partage des synthèses

Les synthèses sont des pages Markdown dans `docs/veille/`, publiées automatiquement sur ce site par la CI. Ce format respecte les recommandations d'accessibilité suivies pour toute la documentation : titres hiérarchisés, langue déclarée, liens explicites.

## Sources

Les sources retenues et leur évaluation sont détaillées dans la page [Sources de veille](sources.md). Le fichier [sources.opml](sources.opml) permet d'importer tous les flux d'un coup dans l'agrégateur choisi.

## Synthèses publiées

*Aucune pour l'instant.* La première synthèse sera publiée après la première séance.

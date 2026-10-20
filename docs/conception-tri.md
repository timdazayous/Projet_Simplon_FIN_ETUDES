# Conception du tri

**Statut** : validée par le développeur le 20 octobre 2026 · **Issue** : #6 · **Compétences** : C14 (spécifications fonctionnelles), C15 (architecture), C7 (choix d'un usage raisonné de l'IA)

Cette page explique **comment** un ticket ou une alerte est trié. Les étiquettes elles-mêmes sont définies dans la page [Taxonomie](taxonomie.md).

## Le principe : combiner des règles et un modèle

Deux approches étaient possibles :

- **tout confier au modèle** : conception simple, mais le modèle doit tout deviner, y compris ce que l'on sait déjà ;
- **multiplier les files d'entrée** pour trier en amont : moins de travail pour le modèle, mais les utilisateurs se trompent de canal, et une file mal alimentée reste à trier à la main.

Le projet **combine les deux**, chacune là où elle est la plus efficace :

| Élément entrant | Traitement | Pourquoi |
|---|---|---|
| **Alerte de supervision** (connecteur ou adresse mail dédiée) | **Règles** : table de correspondance du type de contrôle vers la catégorie, de la gravité vers la priorité | Texte structuré et source toujours identique : une règle est fiable, explicable et quasi gratuite |
| **Texte libre** (mails, portail, messages internes) | **Modèle** de classification, qui reçoit le canal d'entrée comme indice | Formulations libres et variées, et clients qui se trompent parfois de canal : c'est là que l'apprentissage automatique apporte de la valeur |
| Alerte de supervision **sans règle correspondante** | **Modèle**, en dernier recours | Aucune alerte n'est laissée sans proposition |

Ce choix limite l'usage de l'apprentissage automatique aux cas où il est utile, ce qui réduit aussi la consommation de ressources (éco-conception).

## Le canal d'entrée : une information connue

Chaque élément arrive avec sa **source**, connue dès l'arrivée : le connecteur ou l'adresse de réception. Le modèle ne la devine pas, il l'utilise comme indice. Un mail reçu sur l'adresse administrative a de fortes chances d'être administratif, sans que ce soit certain.

| Code | Canal | Exemple |
|---|---|---|
| `monitoring_connector` | Connecteur de supervision (API) | Alerte transmise automatiquement par l'outil de supervision |
| `monitoring_email` | Adresse mail dédiée à la supervision | Alerte envoyée par mail par un équipement ou un outil de supervision |
| `support_email` | Adresse mail du support | « Plus d'Internet depuis ce matin » |
| `admin_email` | Adresse mail administrative | « Question sur la dernière facture » |
| `client_portal` | Portail client | Formulaire de demande |
| `internal` | Message interne au MSP | Demande d'un collaborateur |

**Limite assumée** : les clients se trompent parfois de canal (une panne envoyée à l'adresse administrative, une question de facturation envoyée au support). Le canal reste donc un indice pour le modèle, jamais une décision automatique.

**Écarté** : la téléphonie retranscrite, jugée non nécessaire par le développeur pour ce projet.

## Ce qui est proposé, et par qui

| Étiquette | Alertes de supervision | Texte libre |
|---|---|---|
| Catégorie | règles (type de contrôle) | modèle |
| Type (incident, demande, information) | règles : toujours « incident » | modèle |
| Priorité | règles (gravité de l'alerte, après harmonisation) | modèle |
| Équipe | règles de routage, à partir de la catégorie, du type et de la priorité | règles de routage |

**Le modèle prédit trois étiquettes**, et seulement sur le texte libre. L'équipe est déduite par des règles : le routage reste explicable (« sécurité + P1 → équipe sécurité »), et il y a une étiquette de moins à apprendre. Si les corrections des techniciens montrent que les règles se trompent souvent, l'équipe pourra devenir une étiquette apprise.

## Harmoniser la gravité des outils de supervision

Chaque outil de supervision a ses propres niveaux de gravité. Une **table de correspondance** les ramène aux quatre priorités du projet. Elle est paramétrable et versionnée dans `config/taxonomy.yaml`.

| Outil | Correspondance par défaut (niveau de l'outil → priorité) |
|---|---|
| Zabbix (gravité des déclencheurs) | Disaster → P1 ; High → P2 ; Average → P3 ; Warning, Information, Not classified → P4 |
| Centreon (états) | Hôte DOWN → P1 ; service CRITICAL → P2 ; service WARNING ou UNKNOWN → P3 |
| Meraki | *à compléter* : niveaux à relever dans la documentation de l'outil |

Ces correspondances sont des valeurs par défaut. La priorité réelle peut dépendre de l'équipement (un serveur de production n'est pas un poste de test) : ce raffinement est prévu plus tard, si les corrections des techniciens le justifient.

## La validation par le technicien

Le technicien voit **une seule file, déjà pré-triée**. Pour chaque élément, l'interface affiche les étiquettes proposées et **leur origine** : « règle de supervision » ou « modèle, confiance 87 % ». Le technicien accepte d'un geste, ou corrige ce qui est faux.

Toutes les corrections sont enregistrées, quelle que soit l'origine de la proposition :

- une correction d'une proposition du **modèle** enrichit le jeu de données du prochain ré-entraînement ;
- une correction d'une proposition d'une **règle** signale une règle à revoir.

## Conséquences pour les données

Le générateur de tickets synthétiques et les données récupérées devront respecter cette conception :

- une part d'**alertes de supervision structurées**, au format des outils cités, avec leur gravité d'origine ;
- une part de **texte libre**, sur les différents canaux ;
- une part de **messages arrivés sur le mauvais canal**, pour que le modèle apprenne à ne pas se fier aveuglément à la source.

Les proportions seront fixées avec le générateur.

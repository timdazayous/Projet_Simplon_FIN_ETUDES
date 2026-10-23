# Conception du tri

**Statut** : validée par le développeur le 20 octobre 2026 · **Issue** : #6 · **Compétences** : C14 (spécifications fonctionnelles), C15 (architecture), C7 (choix d'un usage raisonné de l'IA)

Cette page explique **comment** un ticket ou une alerte est trié. Les étiquettes elles-mêmes sont définies dans la page [Taxonomie](taxonomie.md).

## Point de départ : un workflow à base de règles

La conception s'inspire d'un workflow réellement en place dans un MSP, connu du développeur :

1. chaque mail reçu déclenche un traitement automatique qui identifie sa **source** (mail client, outil de supervision…) ;
2. si toutes les informations nécessaires sont présentes, le **ticket est créé automatiquement** avec les bons paramètres, et le mail est archivé dans le dossier du client ;
3. sinon, le mail **reste dans la boîte de réception** et un technicien le traite à la main ;
4. un mail client lié à un ticket existant est **ajouté au ticket comme note** ; s'il semble plus urgent que le ticket, il part dans un **canal de revue de priorité**, où un humain confirme ou non la hausse ;
5. les tickets urgents sont relayés dans un **canal de messagerie dédié**, pour être traités sans attendre.

**Limite de ce workflow** : il repose uniquement sur des règles. Tout mail client qui ne correspond à aucune règle reste à traiter manuellement, et une partie de ces mails n'est pas traitée. **Le projet ajoute une couche d'IA** pour analyser ces textes libres et en traiter automatiquement une bien plus grande part.

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

## Automatisation et intervention humaine

Le but est de **réduire le traitement manuel au maximum**. Les techniciens ne valident pas chaque entrée : un humain n'intervient que lorsque le système n'est pas assez sûr de lui, ou lorsqu'une décision le justifie.

| Situation | Ce que fait le système | Intervention humaine |
|---|---|---|
| Proposition **sûre** : règle de supervision, ou modèle au-dessus du **seuil de confiance** | Crée le ticket dans l'outil de ticketing avec catégorie, type, priorité et équipe, puis archive le message | Aucune : le technicien retrouve le ticket dans sa file habituelle |
| Proposition **incertaine** : modèle sous le seuil, ou informations insuffisantes | Place l'élément dans une **file d'exceptions**, avec une proposition pré-remplie | Un technicien traite l'exception : il accepte la proposition ou la corrige |
| **Message lié à un ticket existant** (même client, même sujet, référence du ticket) | Ajoute le message au ticket comme note | Aucune, sauf si l'urgence semble plus élevée (ligne suivante) |
| Message qui laisse penser à une **urgence plus élevée** que la priorité du ticket | Envoie une demande en **revue de priorité** | Un humain confirme ou refuse la hausse de priorité |
| Ticket **P1** | Notifie le **canal des urgences** | L'équipe concernée le prend en charge sans attendre |

**Exemple de revue de priorité** : la panne d'un serveur secondaire est habituellement traitée en deux ou trois jours. Si le client écrit qu'il en a besoin au plus vite pour une raison urgente, le système le détecte et propose de relever la priorité. Un humain décide.

Cette détection est confiée au **service LLM** (voir [Service LLM](service-llm.md)) : il compare le message au ticket ouvert, repère l'urgence, l'échéance et l'impact métier, et renvoie une proposition structurée avec sa justification. Le classifieur, lui, ne voit qu'un texte isolé et ne sait pas raisonner sur des dates relatives.

**Ce qui n'est jamais automatique** : aucune action n'est exécutée sur les systèmes des clients, aucune réponse n'est envoyée au client, et aucune priorité n'est relevée sans confirmation humaine.

### Le seuil de confiance

Le modèle fournit une confiance pour chaque proposition. Le **seuil** décide de ce qui est automatisé et de ce qui part en exception : plus il est haut, moins il y a d'erreurs automatiques, mais plus il y a d'exceptions à traiter. Il sera fixé à partir de l'évaluation du modèle, en visant un taux d'erreur acceptable sur les tickets créés automatiquement, puis ajusté selon les corrections observées.

### Apprendre sans effort supplémentaire

Les techniciens ne font aucune saisie de plus. Le système apprend de ce qu'ils font déjà :

- les **exceptions traitées** donnent la bonne réponse sur les cas difficiles ;
- les **décisions de revue de priorité** indiquent si la détection d'urgence était juste ;
- les **corrections faites après coup dans l'outil de ticketing** (changement de catégorie, d'équipe ou de priorité d'un ticket créé automatiquement) sont récupérées et signalent une erreur du modèle ou d'une règle.

Ces retours alimentent le ré-entraînement du modèle, ou la révision d'une règle.

## Conséquences pour les données

Le générateur de tickets synthétiques et les données récupérées devront respecter cette conception :

- une part d'**alertes de supervision structurées**, au format des outils cités, avec leur gravité d'origine ;
- une part de **texte libre**, sur les différents canaux ;
- une part de **messages arrivés sur le mauvais canal**, pour que le modèle apprenne à ne pas se fier aveuglément à la source ;
- une part de **messages liés à un ticket existant**, dont certains signalent une urgence plus élevée, pour la revue de priorité.

Les proportions seront fixées avec le générateur.

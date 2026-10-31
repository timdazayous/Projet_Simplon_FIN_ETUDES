# Générateur de tickets et d'alertes synthétiques

**Issue** : #26 · **Compétences** : C1 (préparer des données exploitables, y compris fictives), C3 (homogénéisation du format) · **Code** : `src/data/` · **Configuration** : `config/generator.yaml`

## Rôle

Le générateur fabrique des **messages fictifs** pour combler les manques des jeux publics traduits (voir [Jeux de données publics](donnees/jeux-publics.md)) :

- des **alertes de supervision** (Zabbix, Centreon) : aucun jeu public n'en contient ;
- les catégories peu représentées (`admin_billing`, `procurement`, `telephony`, `backup`, `printing`, `security`), le type `information` et les quatre niveaux de priorité ;
- les cas décrits dans la [Conception du tri](conception-tri.md) : messages arrivés sur le **mauvais canal**, messages **liés à un ticket existant** (dont une part plus urgente, pour la revue de priorité) ;
- des **données personnelles et des secrets fictifs**, pour tester la pseudonymisation et le masquage des secrets ;
- le style d'un MSP français : formules de politesse, outils, noms de clients inventés.

Selon la [répartition du corpus](donnees/corpus.md) (décision du 31 octobre 2026), le générateur fournit **3 118 des 6 000 messages** d'entraînement et de validation (52 %), le public traduit étant limité par catégorie à sa cible, ainsi que 180 messages de test et environ 1 500 alertes de supervision. Le plan initial prévoyait 2 400 messages (40 %) : les catégories rares du public (`messaging`, `accounts`, `printing`, `backup`, `telephony`, `procurement`, `admin_billing`) exigent davantage.

## Principes de fonctionnement

| Principe | Ce que cela veut dire |
|---|---|
| Hors ligne, sans LLM | Les textes viennent de **modèles de phrases** (`src/data/templates.py`) et de variations aléatoires (heures, noms d'hôtes, formules, ton selon le canal). Aucun réseau, aucun quota. |
| Taxonomie = référence unique | Les étiquettes sont lues dans `config/taxonomy.yaml`. Le générateur **refuse de démarrer** si la configuration ou les modèles de phrases utilisent une étiquette inconnue. |
| Équipe calculée, jamais tirée au sort | La fonction `Taxonomy.route_team` (`src/data/taxonomy.py`) applique les règles de routage du fichier YAML. Elle sera réutilisée par la suite (tests, API). |
| Alertes cohérentes | La catégorie d'une alerte est celle des mots-clés de `monitoring_check_category` trouvés dans le nom du contrôle ; la priorité vient de `monitoring_severity`. |
| Reproductible | La graine (`seed`) pilote tous les tirages : même graine et même configuration donnent des fichiers **identiques octet pour octet**. Les alertes ne dépendent pas du nombre de tickets demandé, et inversement. |
| Données fictives repérables | Voir le tableau suivant. |

### Données personnelles fictives

| Donnée | Valeurs produites | Pourquoi |
|---|---|---|
| Adresses mail | Domaines en `.test` (nom réservé par la RFC 2606, jamais résolu) | Impossible de confondre avec une vraie adresse |
| Adresses IP | Plages de documentation de la RFC 5737 : `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` | Jamais routées sur Internet |
| Téléphones | Plages réservées à la fiction par l'ARCEP : `01 99 00 xx xx` et `06 39 98 xx xx` | Numéros qui ne sont attribués à personne |
| Noms et sociétés | Noms de famille et sociétés **inventés** (combinaison de mots de fantaisie) | Ne désignent aucune personne ni entreprise réelle |
| Secrets | Chaînes contenant `FAKE` (par exemple `FAKE-PWD-xxxxxxxxxx`) | Repérables par les tests de détection et de masquage |

Chaque enregistrement contient une liste `pii` des valeurs fictives réellement présentes dans le texte : les tests de pseudonymisation peuvent vérifier qu'aucune ne subsiste après traitement. **Limite** : un nom inventé peut, par hasard, ressembler à un nom réel. Le contrôle fort reste le domaine `.test`.

## Paramètres

Tous les paramètres sont dans `config/generator.yaml`, avec des commentaires. Les valeurs par défaut sont les proportions validées par le développeur le 20 octobre 2026. Les nombres sont des **poids relatifs** (ils n'ont pas besoin de totaliser 100).

| Paramètre | Valeur par défaut | Rôle |
|---|---|---|
| `seed` | 42 | Graine des tirages aléatoires |
| `volumes.free_text` | 2 400 | Nombre de messages de texte libre **du script seul** (`generate_synthetic.py`) ; l'assemblage du corpus impose le besoin par catégorie |
| `corpus.total` | 6 000 | Messages d'entraînement et de validation (public + généré) |
| `corpus.validation_share` | 0,15 | Part de la validation, stratifiée par catégorie |
| `corpus.test_generated` | graine 4 242, 60 par catégorie (`backup`, `procurement`, `admin_billing`) | Test généré, sans vrai ticket de test pour ces catégories |
| `volumes.alerts` | 1 500 | Nombre d'alertes de supervision |
| `clients.count` | 60 | Nombre de clients fictifs (une soixantaine de PME) |
| `free_text.channels` | support 25, portail 10, administratif 5, interne 5 | Canaux d'arrivée du texte libre |
| `free_text.types` | incident 55, demande de service 30, information 15 | Types |
| `free_text.priority_target` | P1 5, P2 20, P3 45, P4 30 | Priorités visées sur l'ensemble du texte libre |
| `free_text.priority_by_type` | voir le fichier | Répartition des priorités par type (voir plus bas) |
| `free_text.wrong_channel_rate` | 0,10 | Part des messages arrivés sur le mauvais canal |
| `free_text.linked_ticket.rate` | 0,15 | Part des messages clients liés à un ticket |
| `free_text.linked_ticket.escalated_share` | 0,33 | Part des messages liés qui sont plus urgents que le ticket |
| `free_text.secret_rate` | 0,05 | Part des messages (de certaines catégories) contenant un faux secret |
| `alerts.sources` | connecteur 40, mail 15 | Canaux de supervision |
| `alerts.tools` | Zabbix 60, Centreon 40 | Outils de supervision |
| `alerts.categories` | voir le fichier | Ressource concernée ; 4 catégories sans mot-clé produisent des alertes **sans règle** |

## Proportions par défaut et justification

| Élément | Proportion | Justification |
|---|---|---|
| Canaux de réception (flux complet) | supervision 55 % (connecteur 40 %, mail 15 %), support 25 %, portail 10 %, administratif 5 %, interne 5 % | Reproduit le flux d'un MSP où la supervision domine, tel que décrit par le développeur (Issue #26) |
| Mauvais canal | 10 % du texte libre | Assez pour que le modèle apprenne à ne pas se fier au seul canal, sans masquer le cas normal |
| Liés à un ticket | 15 % des messages clients | Les relances sont fréquentes dans un vrai MSP |
| Dont plus urgents | un tiers | Cas qui déclenche la revue de priorité, à représenter sans devenir majoritaire |
| Types | 55 / 30 / 15 | Les incidents dominent, les demandes de service viennent ensuite, les demandes d'information sont minoritaires mais indispensables (manque des jeux publics) |
| Priorités | P1 5 %, P2 20 %, P3 45 %, P4 30 % | Les cas critiques sont rares, comme dans la réalité |

**Deux précisions importantes sur ces chiffres.**

1. **Les 55 % de supervision décrivent le flux complet**, pas le corpus d'entraînement. L'Issue demande environ 2 400 messages de texte libre **et** environ 1 500 alertes : les alertes y pèsent donc moins de 40 %. Le générateur produit les deux fichiers séparément ; les poids de canaux de supervision (40 et 15) ne servent qu'à répartir les alertes entre connecteur et mail. Les alertes sont traitées par des règles et n'ont pas besoin du même volume que le texte libre.
2. **Les priorités sont atteintes via une répartition par type.** Un message de type `information` ou `service_request` n'est presque jamais critique, et la règle de routage traite P1 + incident à part. Une matrice (`priority_by_type`) reproduit la cible globale à moins de 2 points, et le générateur le vérifie au démarrage. Les messages « liés plus urgents » ne peuvent pas être P4 (rien de moins urgent à dépasser), ce qui déplace légèrement la répartition réelle (de l'ordre de 2 points sur P3 et P4).

**Mauvais canal.** Un canal général (support, portail, interne) reçoit normalement les catégories techniques ; le canal administratif reçoit `admin_billing` et `procurement`. Un message « mauvais canal » inverse ce lien (une panne envoyée à l'adresse administrative, une question de facturation envoyée au support). Conséquence : la part réelle des catégories administratives est supérieure à leur poids relatif dans la configuration, car le canal administratif ne reçoit qu'elles.

## Format de sortie

Les fichiers sont au format JSONL (un objet JSON par ligne), dans `data/raw/` (dossier ignoré par Git) :

| Fichier | Contenu |
|---|---|
| `synthetic_tickets.jsonl` | Texte libre : `id`, `created_at`, `source`, `subject`, `body`, `language`, `client_id`, `client_name`, `requester`, `category`, `type`, `priority`, `team`, `wrong_channel`, `linked_ticket_ref`, `linked_ticket_priority`, `priority_escalation`, `contains_secret`, `pii`, `origin` |
| `synthetic_alerts.jsonl` | Alertes : `id`, `created_at`, `source`, `tool`, `subject`, `body`, `client_id`, `client_name`, `host`, `ip`, `check_name`, `entity`, `tool_severity`, `category`, `type`, `priority`, `team`, `rule_match`, `pii`, `origin` |

Le couple `subject` / `body` suit celui des jeux publics (Tobi-Bueck : `subject`, `body`, `type`, `queue`, `priority`), pour que l'agrégation soit directe. `rule_match` vaut `false` pour une alerte dont le nom de contrôle ne contient aucun mot-clé de la taxonomie : le modèle devra la traiter en dernier recours.

Un petit échantillon versionné (60 tickets, 30 alertes, graine 7) se trouve dans `tests/fixtures/` : il sert aux tests et montre le format.

## Commandes

Générer le corpus par défaut :

```bash
uv run python scripts/generate_synthetic.py
```

Générer un petit jeu avec une autre graine, dans un autre dossier :

```bash
uv run python scripts/generate_synthetic.py --seed 7 --tickets 100 --alerts 50 --out-dir data/raw/essai
```

Assembler le corpus de classification (le générateur produit alors **le nombre imposé de messages par catégorie**, voir [Assemblage du corpus](donnees/corpus.md)) :

```bash
uv run python scripts/assemble_corpus.py
```

Par programme, `generate(category_counts={"backup": 345, ...})` impose le nombre exact de messages par catégorie (le paramètre `n_tickets` est alors ignoré). Le canal de chaque message est choisi selon la catégorie : canal administratif pour `admin_billing` et `procurement`, canaux généraux pour les autres, avec la même part de « mauvais canal » (10 %). Les alertes ne dépendent pas de ce réglage.

Lancer les tests du générateur :

```bash
uv run pytest tests/test_generator.py tests/test_taxonomy.py
```

La génération par défaut (2 400 textes et 1 500 alertes) prend moins d'une seconde et produit environ 3,3 Mo : aucune précaution particulière pour la mémoire.

## Limites

- **Risque d'apprentissage du style du générateur.** Les textes sont produits par un nombre fini de modèles de phrases. Un classifieur entraîné sur beaucoup de données générées peut apprendre ces formulations plutôt que le sens, et obtenir de bons scores sur des textes générés sans bien fonctionner sur des textes réels. **Parade** : l'évaluation du modèle se fait d'abord sur des **données réelles publiques** (test externe tasksource traduit, test de référence relu par le développeur). La part générée est toutefois de 52 % du corpus d'entraînement et de validation, et trois catégories (`backup`, `procurement`, `admin_billing`) n'ont qu'un **test généré**, optimiste car ses modèles de phrases sont partagés avec l'entraînement (voir [Assemblage du corpus](donnees/corpus.md)).
- Variété limitée : chaque combinaison (catégorie, type) repose sur deux à quatre modèles de phrases (quatre modèles ajoutés en octobre 2026 pour les huit catégories les plus demandées, voir l'Issue #46). Mesure sur les 3 118 messages générés du corpus : 99,8 % de textes distincts, mais **140 objets de message distincts**, soit environ 22 messages par modèle d'objet (110 et 28 avant l'enrichissement). Les paramètres aléatoires (noms, machines, durées, ton) apportent de la variation, mais pas la richesse d'un vrai texte.
- Catégories et priorités tirées **indépendamment du contenu réel** : le texte est cohérent avec ses étiquettes par construction, ce qui rend la tâche plus facile qu'en réalité (pas de message ambigu, hormis les cas « mauvais canal »).
- Les alertes sont en anglais pour Zabbix et Centreon (comme les outils), avec quelques contrôles en français ; Meraki n'est pas généré (niveaux de gravité encore à relever).
- Les numéros d'identifiant de ticket lié (`#12345`) sont fictifs et ne renvoient à aucun ticket réel.

## Évolution possible : reformulation par un LLM

Non implémentée. Une évolution possible serait de faire reformuler une partie des messages par un LLM (Groq ou Ollama) pour augmenter la variété du style. Points d'attention : quotas du plan gratuit de Groq (voir [Service LLM](service-llm.md)), contrôle que la reformulation conserve les étiquettes et les données fictives, et traçabilité de la part de texte reformulé. À envisager seulement si l'évaluation montre un effet de « style du générateur ».

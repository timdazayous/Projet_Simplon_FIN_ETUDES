# Jeux de données publics de tickets de support

**Issue** : #27 · **Compétences** : C1 (contraintes techniques des sources : licence, format, langue, accès), C3 (préparation de l'agrégation et de l'homogénéisation : langue, formats) · **Date de l'étude** : 20 octobre 2026

Aucun jeu de données n'a été téléchargé pour cette étude. Seules les pages de description, les cartes de données (« dataset cards ») et les licences ont été lues. Ce qui n'a pas pu être vérifié est signalé comme tel.

## Objectif

Le développeur a décidé (Issue #26) que la **base principale du corpus** serait constituée de données publiques, traduites en français si besoin. Le générateur de tickets synthétiques s'aligne sur leur format et comble les manques. Cette page répond à trois questions :

1. Quels jeux publics de tickets de support informatique existent, et sous quelle licence ?
2. Lesquels correspondent à notre [taxonomie](../taxonomie.md) et à la [conception du tri](../conception-tri.md) ?
3. Comment les traduire en français sur CPU, sans budget ?

## Critères de sélection

| Critère | Pourquoi |
|---|---|
| Domaine : support informatique, helpdesk ou ITSM | Notre cas d'usage est un MSP. Le service client d'une boutique en ligne n'a pas le même vocabulaire. |
| Licence permettant la réutilisation dans un dépôt public de projet de formation | Le dépôt est public : extraits et jeux dérivés doivent pouvoir y figurer. |
| Étiquettes (catégorie, priorité, type, file) | Le classifieur est supervisé : sans étiquette, le jeu sert peu. |
| Texte libre réaliste | Le modèle doit apprendre des formulations variées. |
| Volume suffisant | Un classifieur à 12 catégories demande plusieurs centaines d'exemples par classe. |
| Données personnelles absentes ou déjà masquées | Règle RGPD du projet. |
| Accès sans achat ni démarche lourde | Zéro budget. |
| Langue : français idéal, sinon traduisible | Les tickets du projet sont en français. |

## Synthèse des candidats

| Jeu | Licence | Langue | Volume | Étiquettes | Origine du texte | Verdict |
|---|---|---|---|---|---|---|
| Tobi-Bueck / customer-support-tickets | CC BY-NC 4.0 | anglais, allemand | 61,8 k lignes (vue Hugging Face) | file, type, priorité, tags | synthétique (selon la carte) | Retenu : base principale, avec réserve sur la licence |
| tasksource / it-support-tickets (Benitez Pereira) | CC BY 4.0 | plusieurs langues, surtout portugais, anglais, allemand, espagnol | 2 229 | 7 catégories | réel, anonymisé | Retenu : jeu de test et complément réaliste |
| decisionmodelhub / support-urgency | CC BY 4.0 | anglais | 800 (200 + 600) | urgent ou non, catégorie de cas | généré par IA | Retenu en complément pour la revue de priorité |
| UCI Incident management process enriched event log | CC BY 4.0 | sans texte | 141 712 événements, 24 918 incidents | priorité, catégorie, impact, urgence | réel (ServiceNow), anonymisé | Retenu comme référence statistique seulement |
| 6StringNinja / synthetic-servicenow-incidents | MIT | anglais | 500 | catégorie (4), urgence, impact, groupe | synthétique | Écarté : trop petit, incohérent |
| siddhantdotexe123 / help-desk-tickets (échantillon) | CC BY-NC 4.0 | anglais | 1 000 tickets (échantillon gratuit) | priorité P1 à P4, équipes | synthétique | Écarté : échantillon d'un produit payant |
| phi-ai-info / support_tickets | MIT | non précisée | 60 (sous-ensemble décrit) ou 1 135 | 10 mots-clés | non décrite | Écarté : trop court et trop artificiel |
| Bitext customer support | CDLA-Sharing-1.0 | anglais | 26 872 | 10 catégories, 27 intentions | hybride synthétique | Écarté : service client e-commerce |

## Fiches des jeux étudiés

### 1. Tobi-Bueck / customer-support-tickets

- **Source** : <https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets>. Un miroir Kaggle existe (« Customer IT Support - Ticket Dataset »), mais la page Kaggle n'a pas pu être lue : sa licence n'est donc **pas vérifiée**.
- **Auteur** : Tobias Bueck (compte Hugging Face). La carte promeut aussi son générateur commercial de tickets synthétiques.
- **Licence** : **CC BY-NC 4.0** (champ `license` de la carte). Elle permet de copier, redistribuer et adapter (donc traduire) le jeu, **avec attribution**, mais **uniquement pour un usage non commercial**. Pour un projet de formation sans but lucratif, un dépôt public contenant des extraits traduits est compatible, à condition de citer l'auteur, d'indiquer les modifications (traduction, ré-étiquetage) et de ne pas laisser croire à une approbation de l'auteur. **Limite** : si l'outil devenait un produit commercial, ces données ne pourraient pas être réutilisées. Le projet est fictif et pédagogique, mais ce point doit figurer dans la documentation.
- **Langue** : anglais et allemand. La carte précise qu'il existe **deux versions** du jeu, la plus récente ayant plus de tickets mais seulement ces deux langues. Un résultat de recherche mentionne aussi du français, de l'espagnol et du portugais pour le miroir Kaggle : **non vérifié**.
- **Volume** : 61,8 k lignes dans la vue Hugging Face (classe de taille « 10K à 100K »).
- **Format** : CSV, avec conversion automatique en Parquet proposée par Hugging Face.
- **Champs** : `subject`, `body`, `answer`, `type` (4 valeurs), `queue` (52 valeurs dans la vue Hugging Face), `priority` (5 valeurs dans la vue), `language`, `version`, `tag_1` à `tag_6` ou plus. La carte (texte) décrit une version plus ancienne : 10 files (Technical Support, Customer Service, Billing and Payments, Product Support, IT Support, Returns and Exchanges, Sales and Pre-Sales, Human Resources, Service Outages and Maintenance, General Inquiry), 3 priorités (Low, Medium, Critical) et 4 types (Incident, Request, Problem, Change). **Les deux descriptions diffèrent** : les valeurs exactes de la dernière version ne sont pas vérifiables sans ouvrir le fichier.
- **Adéquation à la taxonomie** :
    - Types : Incident correspond à `incident` ; Request et Change à `service_request` ; Problem à `incident` (à confirmer) ; **aucun équivalent visible pour `information`**.
    - Priorités : trois niveaux dans la carte contre quatre chez nous. Critical se répartit entre P1 et P2, ce qui impose une règle ou une relecture.
    - Catégories : les files du jeu ne sont pas nos catégories. Seules « IT Support », « Technical Support » et « Service Outages and Maintenance » sont proches de l'informatique ; « Billing and Payments » correspond à `admin_billing`. Les `tags` (mots-clés) permettent un rattachement plus fin à `network`, `accounts`, `software`, etc. Il faudra un **ré-étiquetage** par règles sur les tags, puis un contrôle.
    - Manques : supervision, sauvegarde, téléphonie, sécurité et achats, à confirmer sur les files exactes de la dernière version.
- **Qualité apparente** : texte généré (selon la carte, « synthétique »), donc propre et assez uniforme. La fiabilité des étiquettes n'est pas documentée : la carte n'a pas de section sur les limites.
- **Données personnelles** : la carte ne dit rien sur le sujet pour ce jeu. Des données synthétiques ne devraient pas en contenir, mais **un contrôle automatique (e-mails, téléphones) reste à faire à l'import**.
- **Accès** : téléchargement direct sans compte, aucun accès restreint visible sur la page.

### 2. tasksource / it-support-tickets (Benitez Pereira, 2022)

- **Source** : <https://huggingface.co/datasets/tasksource/it-support-tickets> (copie Hugging Face) ; dépôt d'origine sur Zenodo : <https://zenodo.org/records/7648117> (DOI 10.5281/zenodo.7648117).
- **Auteur** : Leonardo Santiago Benitez Pereira, Instituto Federal de Santa Catarina (Brésil), « Classification of IT Support Tickets », Zenodo, 2022.
- **Licence** : **CC BY 4.0**. Elle permet toute réutilisation, modification (traduction comprise), redistribution et usage dans un dépôt public, même commercial, **à condition de citer l'auteur** et d'indiquer les modifications.
- **Langue** : plusieurs langues, principalement portugais, anglais, allemand et espagnol (Zenodo). Le français n'est pas annoncé.
- **Volume** : 2 229 tickets (1,57 k en entraînement, 657 en test, découpage de l'auteur).
- **Format** : CSV (Zenodo : `X_train`, `X_test`, `y_train`, `y_test`) ou Parquet (Hugging Face), environ 102 ko.
- **Champs** : `text` et `label` (7 classes : Active Directory, Computer-Services, EOL, Fileservice, O365, Software, Support general).
- **Adéquation à la taxonomie** : correspondance proposée ci-dessous. Il n'y a ni priorité ni type : ces étiquettes manquent.

| Classe du jeu | Catégorie proposée |
|---|---|
| Active Directory | `accounts` |
| Computer-Services | `workstation` |
| Fileservice | `infrastructure` |
| O365 | `messaging` |
| Software | `software` |
| EOL | à déterminer : le sens exact de l'abréviation n'est pas expliqué sur les pages lues |
| Support general | trop vague : à ré-étiqueter ou à écarter |

- **Qualité apparente** : **tickets réels** d'une société de support informatique de la région de Florianópolis, classés à la main par trois professionnels. C'est la source la plus proche d'un vrai MSP. Mais le volume est faible, les langues sont mélangées et les textes contiennent des marqueurs de masquage.
- **Données personnelles** : retirées par les auteurs (AWS Comprehend, expressions régulières, vérification manuelle) et remplacées par des balises comme `[NAME]`, `[TICKET ID]`, `[LOCATION]`. Ces balises seront remplacées par des valeurs fictives à l'import. Un balayage automatique reste prudent, car une vérification manuelle n'est jamais garantie à 100 %.
- **Accès** : téléchargement direct, enregistrement marqué « Open » sur Zenodo.

### 3. decisionmodelhub / support-urgency

- **Source** : <https://huggingface.co/datasets/decisionmodelhub/support-urgency>.
- **Licence** : **CC BY 4.0** (mêmes droits que ci-dessus, avec attribution).
- **Langue** : anglais. **Volume** : 800 cas (200 de développement, 600 de test) et un sous-ensemble de résultats d'environ 4 000 lignes.
- **Champs** : `case_id`, `facts`, `expected` (« urgent » ou « no »), `category` (urgent, near_miss, request), `difficulty`, `label_rationale`, etc.
- **Adéquation** : ne concerne que l'**urgence**. Utile pour amorcer et tester la détection de messages « plus urgents » (revue de priorité), pas pour la catégorie ni l'équipe.
- **Qualité** : généré par IA à partir de fiches de faits, étiquettes attribuées par règles puis relues par un modèle (champs `source` et `label_provenance`). Cette chaîne est déclarée sur la carte, **non auditée**. Petit volume.
- **Données personnelles** : non mentionnées ; données générées. **Accès** : direct.

### 4. UCI Incident management process enriched event log

- **Source** : <https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log> (Amaral, Fantinato, Peres, 2018 ; DOI 10.24432/C57S4H).
- **Licence** : **CC BY 4.0**.
- **Contenu** : 141 712 événements pour 24 918 incidents d'une instance ServiceNow, 36 attributs (priorité, catégorie, impact, urgence, dates…). Fichier CSV de 44,1 Mo (zip de 2,3 Mo). Anonymisé.
- **Limite décisive** : **aucun champ de texte** (les champs textuels ont été retirés). Il ne permet donc pas d'entraîner un classifieur de texte.
- **Utilité** : calibrer les **proportions de priorité et de catégorie** et la saisonnalité du générateur sur des chiffres réels. Anglais, accès direct.

### 5. 6StringNinja / synthetic-servicenow-incidents (écarté)

- **Source** : <https://huggingface.co/datasets/6StringNinja/synthetic-servicenow-incidents>. **Licence** : MIT (très permissive, avec conservation de la mention de licence dans les copies).
- **Contenu** : 500 incidents synthétiques en anglais (`number`, `short_description`, `description`, `resolution`, `urgency`, `impact`, `category` en 4 valeurs, `assignment_group` en 2 valeurs). Format Parquet.
- **Raisons d'écart** : volume trop faible, 4 catégories seulement, la carte contient encore un paramètre non rempli (`{N}`), et de nombreuses résolutions ne correspondent pas à la description (constat fait sur la page lue). Les données ne sont pas assez fiables pour entraîner un modèle. Son schéma (numéro, urgence, impact, groupe) reste une **inspiration pour le format du générateur**.

### 6. siddhantdotexe123 / help-desk-tickets (écarté)

- **Source** : <https://huggingface.co/datasets/siddhantdotexe123/help-desk-tickets> (copie : <https://huggingface.co/datasets/Harshdj18/help-desk-tickets>, dupliquée de mindweave/help-desk-tickets). Éditeur : Mindweave Technologies.
- **Licence** : CC BY-NC 4.0 pour l'échantillon.
- **Contenu** : échantillon gratuit de 1 000 tickets (3 018 lignes sur 4 tables) d'un jeu synthétique de 10 000 tickets vendu sur Gumroad. Priorités P1 à P4 et équipes proches des nôtres (tier-1, tier-2, identity, network, security, collaboration).
- **Raisons d'écart** : l'échantillon sert de **démonstration commerciale** ; le jeu complet est payant (contrainte de budget nul) ; la carte ne détaille pas les colonnes des tickets ; licence non commerciale ; les noms de personnes ne sont pas explicitement confirmés comme fictifs. Les priorités P1 à P4 confirment toutefois qu'un tel schéma est courant.

### 7. phi-ai-info / support_tickets (écarté)

- **Source** : <https://huggingface.co/datasets/phi-ai-info/support_tickets>. **Licence** : MIT.
- **Contenu** : sous-ensemble « nano » de 60 exemples décrit par la carte (et un sous-ensemble « alpha » d'environ 1 080 lignes), textes de 10 à 83 caractères, 10 mots-clés (accès, utilisateurs, disque). Langue et origine non précisées.
- **Raisons d'écart** : trop court, textes trop pauvres (quelques mots), peu de catégories, origine non documentée.

## Jeux écartés pour d'autres raisons

| Jeu | Raison |
|---|---|
| Bitext customer support (<https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset>), licence CDLA-Sharing-1.0, 26 872 paires | Service client générique (commandes, remboursements, livraison), anglais, 10 catégories sans rapport avec l'informatique. La licence impose en plus le partage des données dérivées dans les mêmes conditions. |
| Kaggle « IT Support Tickets » (<https://www.kaggle.com/datasets/ahsanneural/synthetic-it-support-tickets>) | Page illisible par l'outil de lecture (contenu chargé par JavaScript) : **licence, volume et champs non vérifiés**. Écarté faute de pouvoir vérifier ; à revoir à la main si besoin. |
| Modèles de classification publiés sur Hugging Face (par exemple DavinciTech/BERT_Categorizer, jeremiasdavison/it-support-ticket-classifier) | Ce sont des modèles, non des jeux. L'un est entraîné sur des données privées, l'autre sur Tobi-Bueck. Hors périmètre : le classifieur doit être entraîné dans le projet. |
| Jeux de tickets informatiques en français | Recherche faite : **aucun jeu français ouvert n'a été trouvé** (recherche web limitée, l'absence n'est pas prouvée). |

## Options de traduction vers le français

Contraintes : CPU seulement, zéro budget. Les jeux étudiés sont publics, donc leur envoi à Groq ne pose pas de problème de données personnelles ; la règle de pseudonymisation avant envoi externe reste valable pour les vrais tickets ultérieurs.

| Option | Licence et existence vérifiées | Qualité attendue | Temps estimé | Contraintes |
|---|---|---|---|---|
| **OPUS-MT** (Helsinki-NLP) : `opus-mt-en-fr`, `opus-mt-de-fr`, `opus-mt-es-fr` | Apache-2.0, pages vérifiées | Correcte sur des phrases courantes. BLEU publiés (jeux de presse) : 27 à 40 (anglais vers français), 25 à 37 (allemand vers français), 32 à 35 (espagnol vers français). Les sigles et messages d'erreur peuvent être mal rendus. | Voir l'estimation plus bas : de l'ordre de quelques heures pour 20 000 tickets | Un modèle par langue source, donc une détection de langue préalable. Un modèle portugais vers français : **non vérifié**. Avec Transformers, la page recommande de charger le modèle directement (le pipeline de traduction n'est pas géré en v5). |
| **CTranslate2** (moteur d'inférence) avec les modèles OPUS-MT convertis | Licence MIT (affichée sur le dépôt), conversion Marian/OPUS-MT annoncée | Même qualité qu'OPUS-MT (BLEU 27,92 contre 27,90 dans leur banc d'essai) | Banc d'essai de CTranslate2 : 525 tokens/s contre 147 pour Transformers, avec 4 threads sur une machine AWS c5.2xlarge ; 696 tokens/s en int8. **Valable pour leur configuration uniquement.** | Une étape de conversion et une dépendance de plus. |
| **Groq** (client du projet, `openai/gpt-oss-20b`) | Quotas du plan gratuit lus sur la page officielle : 30 requêtes par minute, 1 000 requêtes et 200 000 tokens par jour, 8 000 tokens par minute | Probablement la meilleure : un LLM comprend le contexte et peut respecter un format. | Limité par les 200 000 tokens par jour : avec environ 500 à 800 tokens par ticket (**hypothèse** ; jusqu'à 500 tokens de raisonnement ont été observés, voir `docs/service-llm.md`), cela fait **environ 250 à 400 tickets par jour** : plusieurs semaines pour 10 000 tickets. | Quotas stricts, erreurs 429 (gérées par le client), dépendance à un service externe dont le plan gratuit peut changer. |
| **Ollama** local (`gemma3:4b`, déjà utilisé comme secours) | Modèle déjà retenu dans le projet | À mesurer | **Non mesuré pour la traduction.** Sur CPU, un appel prend plusieurs secondes (voir `docs/service-llm.md`) ; multiplié par le nombre de tickets, c'est lent. | Charge importante sur le poste, sans quota. |
| **NLLB-200 distillé (600 M)** de Meta | Licence **CC-BY-NC-4.0** (vérifiée), modèle « de recherche, non destiné à la production » | Bonne couverture multilingue | Non estimé | Licence non commerciale et cadre d'usage restreint. Écarté. |
| Traduction manuelle | sans objet | sans objet | sans objet | Contraire à la décision du développeur. |

**Estimation du temps avec OPUS-MT** (hypothèses explicites) : 20 000 tickets de 150 tokens environ, soit 3 millions de tokens. Avec CTranslate2 à environ 525 tokens/s : environ 6 000 s, soit 1 h 40. Avec Transformers à environ 147 tokens/s : environ 5 h 40. En doublant par prudence (poste plus lent que le banc d'essai, détection de langue) : environ **3 à 12 heures**, à lancer en tâche de fond. Ces chiffres sont des **estimations non mesurées** ; une mesure sur 100 tickets doit précéder le lancement.

**Impact sur les étiquettes** : la traduction ne change pas les étiquettes, mais elle peut déformer les termes techniques (« Active Directory », noms d'erreurs). La liste des termes à ne pas traduire sera définie lors de l'implémentation.

## Recommandation

### Jeux retenus

- **Entraînement (base principale)** : Tobi-Bueck, après filtrage sur les files informatiques et ré-étiquetage vers notre taxonomie. Volume très supérieur au besoin. Réserve : licence non commerciale, à citer dans le README et dans la documentation.
- **Entraînement complémentaire et test** : tasksource / it-support-tickets, pour son réalisme (tickets réels, classés par des professionnels) et sa licence CC BY. Le découpage de test de l'auteur (657 tickets) sert de **jeu de test externe**.
- **Revue de priorité** : decisionmodelhub / support-urgency, en complément pour la détection d'urgence. Petit volume.
- **Calibrage du générateur** : UCI Incident log, pour les répartitions de priorité et de catégorie. Il ne sert pas de corpus.

### Traduction recommandée

1. **OPUS-MT avec CTranslate2** pour le traitement en masse (anglais, allemand, espagnol vers français) : gratuit, local, licence permissive, pas de quota.
2. **Groq** réservé aux **tickets du jeu de test relu** (environ 50 à 300) : meilleure qualité sur peu de volume, compatible avec les quotas du plan gratuit.
3. Une étape de **détection de langue** précède la traduction ; les langues sans modèle vérifié (portugais) sont traitées par Groq, ou écartées.
4. Mesurer d'abord sur 100 tickets (temps, relecture de 20 traductions) avant de lancer le traitement complet.

**Alternative écartée** : Groq pour tout le corpus, trop lent à cause du quota quotidien en tokens.

### Manques que le générateur doit combler

- Alertes de supervision (Zabbix, Centreon, Meraki) : aucun jeu public texte ne les couvre. Elles sont traitées par des **règles** et entièrement générées (55 % du flux selon #26).
- Catégories `admin_billing`, `procurement`, `telephony`, `backup`, `printing` et `security` : peu ou pas présentes dans les jeux retenus (à confirmer sur les files exactes du jeu récent).
- Type `information` et quatre niveaux de priorité (le jeu principal en a trois).
- Messages envoyés sur le **mauvais canal** (10 % du texte libre).
- Messages **liés à un ticket existant** (15 % des messages clients, dont un tiers plus urgents).
- Données personnelles **fictives**, pour tester la pseudonymisation.
- Style MSP : noms de clients fictifs, outils (Autotask, Zabbix), formules de politesse françaises.

### Répartition proposée du corpus

Ces chiffres sont une **proposition à valider** : le volume cible reste une décision ouverte du développeur. Ils prennent pour base 6 000 messages de texte libre pour l'entraînement et la validation, hors alertes de supervision.

| Partie | Part | Messages | Origine |
|---|---|---|---|
| Entraînement et validation, texte libre | 100 % | 6 000 | public traduit et généré |
| dont public traduit (Tobi-Bueck, tasksource, support-urgency) | 60 % | 3 600 | traduction OPUS-MT |
| dont généré aligné sur le format public (manques, mauvais canal, liés à un ticket, personnes fictives) | 40 % | 2 400 | générateur |
| Test externe (découpage de l'auteur de tasksource, traduit) | sans objet | environ 650 | public, non relu message par message |
| **Test de référence relu par le développeur** | sans objet | **50** | moitié public traduit, moitié généré, pré-étiquetés |
| Alertes de supervision, pour tester les règles | sans objet | environ 1 500 | 100 % généré (formats Zabbix, Centreon) |

Les tickets des jeux de test ne doivent **jamais** figurer dans l'entraînement (pas de fuite). L'ensemble des textes publics passe par le contrôle de données personnelles du projet avant tout usage.

## Points incertains

- Valeurs exactes des files, types et priorités de la **dernière version** de Tobi-Bueck (la carte et la vue Hugging Face diffèrent).
- Présence éventuelle de français dans ce jeu (non vérifiée).
- Licence et contenu des jeux Kaggle (pages illisibles).
- Sens de la classe « EOL » et langue exacte des tickets de tasksource.
- Existence et licence d'un modèle OPUS-MT portugais vers français.
- Temps de traduction : estimations, non mesurées.
- Aucun jeu n'a été téléchargé : la qualité réelle du texte n'est pas évaluée.

## Sources

Pages consultées le 20 octobre 2026.

- Tobi-Bueck, customer-support-tickets : <https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets> et son fichier de carte <https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/raw/main/README.md>
- Kaggle, Customer IT Support - Ticket Dataset : <https://www.kaggle.com/datasets/tobiasbueck/multilingual-customer-support-tickets/data> (page illisible)
- tasksource, it-support-tickets : <https://huggingface.co/datasets/tasksource/it-support-tickets>
- Zenodo, Classification of IT Support Tickets : <https://zenodo.org/records/7648117>
- decisionmodelhub, support-urgency : <https://huggingface.co/datasets/decisionmodelhub/support-urgency>
- UCI, Incident management process enriched event log : <https://archive.ics.uci.edu/dataset/498/incident+management+process+enriched+event+log>
- 6StringNinja, synthetic-servicenow-incidents : <https://huggingface.co/datasets/6StringNinja/synthetic-servicenow-incidents>
- siddhantdotexe123, help-desk-tickets : <https://huggingface.co/datasets/siddhantdotexe123/help-desk-tickets>
- Harshdj18, help-desk-tickets : <https://huggingface.co/datasets/Harshdj18/help-desk-tickets>
- phi-ai-info, support_tickets : <https://huggingface.co/datasets/phi-ai-info/support_tickets>
- Bitext, customer support : <https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset>
- Kaggle, IT Support Tickets : <https://www.kaggle.com/datasets/ahsanneural/synthetic-it-support-tickets> (page illisible)
- DavinciTech, BERT_Categorizer : <https://huggingface.co/DavinciTech/BERT_Categorizer>
- jeremiasdavison, it-support-ticket-classifier : <https://huggingface.co/jeremiasdavison/it-support-ticket-classifier>
- OPUS-MT anglais vers français : <https://huggingface.co/Helsinki-NLP/opus-mt-en-fr>
- OPUS-MT allemand vers français : <https://huggingface.co/Helsinki-NLP/opus-mt-de-fr>
- OPUS-MT espagnol vers français : <https://huggingface.co/Helsinki-NLP/opus-mt-es-fr>
- NLLB-200 distillé 600 M : <https://huggingface.co/facebook/nllb-200-distilled-600M>
- CTranslate2 : <https://github.com/OpenNMT/CTranslate2>
- Limites de Groq : <https://console.groq.com/docs/rate-limits>
- Pages du projet : [Taxonomie](../taxonomie.md), [Conception du tri](../conception-tri.md), [Service LLM](../service-llm.md)

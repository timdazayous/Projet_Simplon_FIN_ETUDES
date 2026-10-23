# Récupération et traduction des jeux publics

**Issue** : #29 (phase 1 : script, échantillon, mesures) · **Compétences** : C1 (extraction depuis un fichier et un service web, filtrage, script structuré), C3 (homogénéisation de la langue et des formats, suppression des entrées corrompues) · **Date** : 21 octobre 2026

Cette page décrit comment les jeux publics retenus dans l'[inventaire](jeux-publics.md) sont récupérés, nettoyés puis traduits en français. Elle contient aussi les **mesures réelles** de traduction sur le poste du développeur, et les options pour la suite.

**Périmètre de cette étape** : le script est écrit et testé, et la traduction a été mesurée sur des échantillons de 50 tickets. **La traduction complète n'a pas été lancée.** Le développeur décidera ensuite où la lancer, au vu des mesures.

## Résumé

- Trois jeux sont récupérés depuis Hugging Face : un pour l'entraînement, un pour le test externe, un en complément pour la revue de priorité.
- La licence de chaque jeu est **vérifiée sur la carte Hugging Face avant tout téléchargement**. Si elle diffère de celle attendue, le script s'arrête.
- Après nettoyage et tirage reproductible, il reste **3 600 tickets d'entraînement, 473 tickets de test externe et 800 cas d'urgence**, soit environ 1,9 million de caractères à traduire.
- Sur CPU, avec 4 threads, la traduction de 50 tickets prend **de 50 à 61 secondes** (environ une seconde par ticket). L'extrapolation donne **environ 1 h 20 à 1 h 45** pour tout le corpus. C'est bien moins que les « quelques heures » estimées dans l'inventaire.
- Le poste n'est pas saturé : le processus utilise environ un tiers du processeur et au plus 1,8 Go de mémoire.
- Les règles de correspondance des étiquettes vers notre taxonomie sont **une proposition à valider** (voir plus bas).

## Dépendances et installation

Les bibliothèques lourdes sont dans des **groupes uv séparés**. L'installation de base et la CI ne les installent pas, et les tests n'en ont pas besoin.

| Groupe uv | Contenu | Sert à |
|---|---|---|
| `data` | `huggingface-hub`, `pyarrow`, `psutil` | Récupération des jeux, lecture des fichiers Parquet, mesure de la charge |
| `translate` | le groupe `data`, plus `torch`, `transformers`, `sentencepiece` | Traduction OPUS-MT |

Sous Linux, `torch` est pris sur l'index CPU de PyTorch (déclaré dans `pyproject.toml`), pour ne pas télécharger plusieurs gigaoctets de bibliothèques CUDA. Sous Windows, le paquet de PyPI est déjà sans GPU.

```
uv sync --group dev --group translate
```

Pour revenir à l'installation de la CI : `uv sync --locked --group dev`.

## Commandes

Étape 1 : récupérer, nettoyer et échantillonner (groupe `data`).

```
uv run --group data python scripts/fetch_public_datasets.py
uv run --group data python scripts/fetch_public_datasets.py --only it_support --limit 50
```

Étape 2 : traduire (groupe `translate`). Un seul processus de traduction à la fois.

```
uv run --group translate python scripts/translate_public.py --dataset it_support --limit 50
uv run --group translate python scripts/translate_public.py --dataset customer_support --threads 4 --resume
```

| Option | Rôle |
|---|---|
| `--limit N` | Ne traduit que N tickets, répartis entre les langues présentes (tirage à graine fixe) |
| `--threads N` | Nombre de threads de calcul de torch (4 par défaut, pour laisser de la place au reste du poste) |
| `--batch-size N` | Nombre de segments traduits ensemble (8 par défaut) |
| `--beams N` | Largeur de la recherche en faisceau : 1 est plus rapide, 4 est plus fidèle (2 par défaut) |
| `--min-ram-mb N` | Seuil du garde-fou mémoire (1 500 Mo par défaut) |
| `--resume` | Reprend après un arrêt, sans retraduire les tickets déjà faits |

Toute la configuration (jeux, licences attendues, graine, modèles) est dans `config/public_datasets.yaml`.

## Ce que fait le script de récupération

| Étape | Détail |
|---|---|
| Initialisation | Lecture de `config/public_datasets.yaml` et de la proposition de correspondance des étiquettes. Un nom de jeu inconnu arrête le script avec un message clair. |
| Vérification de la licence | La licence lue sur la carte du jeu doit être celle attendue (`cc-by-nc-4.0` ou `cc-by-4.0`). Sinon : refus avant tout téléchargement, code de sortie 3. |
| Téléchargement | Via `huggingface_hub`, avec un cache local dans `data/raw/public/_hf_cache/` (ignoré par Git). Une erreur réseau ou de format sur un jeu est signalée sans effacer ce qui est déjà enregistré pour les autres. |
| Nettoyage et filtrage | Voir le tableau suivant. |
| Échantillonnage | Tirage reproductible : même graine (42) et mêmes données donnent le même résultat. |
| Étiquettes | Les étiquettes d'origine sont conservées telles quelles. Les étiquettes proposées pour notre taxonomie sont ajoutées à côté. |
| Sauvegarde | Fichiers JSONL dans `data/raw/public/`, écrits de façon atomique (fichier temporaire puis renommage), plus un rapport `prepare_report.json` avec les comptes de chaque étape. |

Les fichiers de sortie sont dans `data/raw/public/`, un dossier **ignoré par Git** : aucun jeu de données n'entre dans le dépôt.

### Choix de nettoyage

Le premier motif rencontré l'emporte : chaque ligne écartée est comptée une seule fois.

| Règle | Pourquoi | Tobi-Bueck | tasksource | urgence |
|---|---|---|---|---|
| Files non informatiques écartées (Customer Service, Billing, Sales…) | Hors sujet pour un MSP. Seules Technical Support, IT Support et Service Outages and Maintenance sont gardées. | 15 644 | sans objet | sans objet |
| Ligne illisible (étiquette absente ou hors des classes) | Impossible à relier à une étiquette d'origine | 0 | 0 | 0 |
| Texte vide | Rien à classer | 0 | 0 | 0 |
| Texte corrompu (caractères de remplacement `U+FFFD`, accents mal encodés) | Le modèle de traduction recopierait les erreurs | 0 | 2 | 0 |
| Texte trop court (moins de 20 ou 10 caractères selon le jeu) | Pas assez de contenu | 0 | 12 | 0 |
| Texte trop long (plus de 4 000 caractères) | Rare, coûteux à traduire, souvent du bruit | 0 | 0 | 0 |
| Langue absente de la liste du jeu, ou indécidable | Pas de modèle de traduction, ou texte trop court pour savoir | 0 | 64 | 0 |
| Doublon exact (casse et espaces ignorés) | Évite de compter deux fois le même ticket, et une fuite entre entraînement et test | 1 | 106 | 0 |
| **Gardés avant tirage** | | **12 942** | **473** | **800** |
| **Gardés après tirage** | | **3 600** | **473** | **800** |

Autres opérations d'homogénéisation, appliquées à tous les textes :

- normalisation Unicode (NFC), retours à la ligne unifiés, espaces insécables et espaces multiples ramenés à un espace, caractères de contrôle supprimés ;
- le CSV de Tobi-Bueck contient des `\n` écrits en toutes lettres (barre oblique inversée suivie de la lettre n) : ils sont remplacés par de vrais retours à la ligne ;
- dans tasksource, le début répété par l'outil de ticketing (« [TICKET ID] - New Support Ticket received - ») est retiré, car il ne porte aucune information ;
- un seul fichier est utilisé pour Tobi-Bueck : la nouvelle version du jeu (28 587 lignes). L'ancienne version (20 000 lignes) en est en grande partie un sous-ensemble.

### Constats sur les données

Ces constats viennent de l'ouverture réelle des fichiers, ce que l'inventaire n'avait pas fait.

- **La langue annoncée est parfois fausse.** Dans les files informatiques de Tobi-Bueck, **1 602 tickets déclarés « de » (allemand) sont écrits en anglais**, soit près de 30 % des 5 600 tickets déclarés allemands. Les traduire avec le modèle allemand les laisse presque inchangés (constaté sur un premier échantillon). Le script détecte la langue sur le texte et **corrige** l'étiquette de langue (1 603 corrections au total, comptées dans le rapport sous `language_corrected`). Après correction, l'échantillon de 3 600 tickets contient 2 521 tickets anglais et 1 079 allemands.
- **Le contenu de Tobi-Bueck est peu « MSP ».** Les tickets sont synthétiques et parlent souvent de marketing, de santé ou de plateformes SaaS, avec des étiquettes (tags) aléatoires. Le jeu sert à apprendre la forme d'un ticket, pas le métier d'un MSP : les 40 % de tickets générés par le projet restent indispensables.
- **tasksource contient beaucoup de quasi-doublons** (tickets automatiques identiques à un numéro près) : 106 doublons exacts sur 657 une fois les balises ignorées.
- **Des alertes de supervision** (check_mk, ping) sont mélangées aux tickets de tasksource. Elles sont conservées, avec leurs étiquettes d'origine.

La langue de tasksource est détectée par une méthode volontairement simple (mots courants et lettres distinctives, sans bibliothèque ajoutée). Elle est testée sur des exemples, mais **sa précision n'a pas été mesurée sur un échantillon relu à la main**. Les 64 textes trop courts ou ambigus sont écartés plutôt que devinés.

## Format de sortie

Un fichier JSONL par jeu, une ligne par ticket. Même esprit que les tickets générés (`id`, `subject`, `body`, `origin`), avec la traçabilité en plus.

| Champ | Contenu |
|---|---|
| `id` | Identifiant stable du projet (`PUB-CS-00001`, `PUB-ITS-00001`, `PUB-URG-00001`) |
| `dataset`, `origin_id` | Jeu d'origine et position dans le fichier d'origine (ou identifiant du cas) |
| `split`, `role` | Découpage d'origine, et rôle dans le projet (entraînement, test, complément) |
| `language_source` | Langue du texte d'origine, après correction |
| `subject`, `body` | Texte d'origine nettoyé |
| `subject_fr`, `body_fr` | Texte traduit (après l'étape de traduction) |
| `original_labels` | Étiquettes d'origine, **inchangées** |
| `proposed_labels` | Catégorie, type et priorité proposés, règle utilisée, indicateur de doute |
| `translation_model`, `translation_flags` | Modèle utilisé, et alertes éventuelles (balise non restituée) |
| `license`, `origin` | Licence du jeu, et `public` |

## Traduction

### Modèles

| Langue source | Modèle | Licence | Taille téléchargée |
|---|---|---|---|
| Anglais | `Helsinki-NLP/opus-mt-en-fr` | Apache-2.0 | environ 290 Mo |
| Allemand | `Helsinki-NLP/opus-mt-de-fr` | Apache-2.0 | environ 293 Mo |
| Espagnol | `Helsinki-NLP/opus-mt-es-fr` | Apache-2.0 | environ 321 Mo |
| Portugais | `Helsinki-NLP/opus-mt-tc-bible-big-mul-deu_eng_fra_por_spa` | Apache-2.0 | environ 900 Mo |

La licence de chaque modèle est indiquée sur sa fiche Hugging Face et a été relue le 21 octobre 2026.

**Il n'existe pas de modèle portugais vers français dédié** (recherche faite dans l'organisation Helsinki-NLP). Le modèle multilingue ci-dessus est le seul trouvé : il traduit vers l'allemand, l'anglais, le français, le portugais et l'espagnol, à condition de préfixer la phrase du jeton de langue cible `>>fra<<`. Il est plus gros (235 millions de paramètres) et **nettement plus lent** (environ 90 caractères par seconde, contre 190 à 475 pour l'espagnol, l'allemand et l'anglais, sur de petits échantillons). Il ne sert que pour 75 tickets de tasksource. Alternative écartée : passer par l'anglais (portugais vers anglais, puis anglais vers français), qui double le temps et cumule les erreurs.

### Choix de mise en œuvre

| Choix | Raison | Alternative écartée |
|---|---|---|
| Découpage des textes en segments de 400 caractères au plus (lignes, puis phrases) | Les modèles Marian traduisent des phrases, pas des pages. Des segments courts se groupent mieux sur CPU. Le texte se recolle à l'identique (testé). | Traduire le ticket entier : risque de troncature à 512 jetons |
| Balises de masquage (`[NAME]`, `[TICKET ID]`…) remplacées par un code neutre avant traduction, puis restituées | Sans protection, le modèle les traduit (`[NOM]`, `[IDET TICKET]`) ou les déforme. Avec le code, toutes sont restituées sur les échantillons ; un code abîmé serait signalé par `tag_not_restored`. | Laisser les balises : constaté défaillant sur l'échantillon |
| 4 threads de calcul, lots de 8 segments, recherche en faisceau de largeur 2 | Laisse de la place au reste du poste. Largeur 2 : bon compromis, largeur 4 coûte environ 15 à 40 % de temps en plus (voir mesures). | Tous les cœurs : poste déjà chargé |
| Un seul modèle en mémoire à la fois, tickets traités langue par langue | Limite la mémoire (au plus 1,8 Go pour le modèle portugais) | Tous les modèles chargés ensemble |
| Écriture de la sortie par petits groupes de 10 tickets, option `--resume` | Un arrêt (garde-fou, veille, coupure) ne fait rien perdre | Écrire à la fin seulement |
| Sans bibliothèque d'optimisation (CTranslate2) pour l'instant | Une dépendance et une étape de conversion de moins. À reconsidérer seulement si le temps mesuré est un problème, ce qui n'est pas le cas. | CTranslate2 (annoncé 3 à 4 fois plus rapide dans son propre banc d'essai, **non mesuré ici**) |

### Garde-fou mémoire

Avant chaque lot, le script lit la mémoire disponible du système. Si elle passe **sous 1 500 Mo**, il s'arrête proprement : ce qui est déjà traduit est enregistré, le rapport indique `stopped_low_memory`, et le code de sortie est 4. Le même contrôle est fait avant et après le chargement d'un modèle. Le seuil se change avec `--min-ram-mb`. Le comportement est testé avec une mémoire simulée.

## Mesures sur le poste

**Poste** : Windows 11, sans GPU, 12 cœurs logiques, 15 Go de mémoire. Au moment des mesures, il restait entre 2,6 et 4,7 Go de mémoire libre : le poste était déjà chargé (navigateur, outils de développement).

**Méthode** : 50 tickets par échantillon, répartis à parts égales entre les langues présentes (tirage à graine fixe), 4 threads, lots de 8, largeur de faisceau 2 sauf indication contraire. Le processus est échantillonné toutes les 2 secondes (mémoire disponible du système, mémoire du processus, processeur du système et du processus). Les modèles étaient déjà téléchargés : **les temps ne comprennent pas le téléchargement**, mais comprennent le chargement du modèle (2 à 5 secondes par langue). Un seul processus de traduction à la fois.

### Résultats

| Mesure | Tobi-Bueck (25 en + 25 de) | tasksource (13 en, 13 de, 12 es, 12 pt) | Tobi-Bueck, faisceau 4 |
|---|---|---|---|
| Caractères traduits | 19 787 | 6 137 | 19 787 |
| Temps total | 61,2 s | 52,8 s | 69,4 s |
| Temps par ticket | 1,22 s | 1,06 s | 1,39 s |
| Débit | 0,82 ticket et 323 caractères par seconde | 0,95 ticket et 116 caractères par seconde | 0,72 ticket et 285 caractères par seconde |
| Mémoire du processus, maximum | 749 Mo | 1 837 Mo (modèle portugais) | 773 Mo |
| Mémoire disponible du système, minimum | 3 738 Mo | 2 657 Mo | 4 074 Mo |
| Processeur du système, moyenne et maximum | 32 % et 42 % | 29 % et 40 % | 36 % et 66 % |
| Processeur du processus (part de la machine entière), moyenne et maximum | 23 % et 33 % | 24 % et 33 % | 29 % et 34 % |

Sur Tobi-Bueck, les temps varient d'une exécution à l'autre : **50,4 s et 61,2 s** pour la même mesure (largeur 2), selon la charge du poste à ce moment. Une extrapolation fiable à ±20 % est donc le mieux que ces mesures permettent.

Débit par langue (caractères par seconde, chargement du modèle retiré, largeur 2) : anglais 475 (Tobi-Bueck) et 215 (tasksource, textes très courts) ; allemand 288 et 66 ; espagnol 189 ; portugais 90. Les chiffres sur tasksource reposent sur très peu de caractères et surestiment le coût par caractère, car chaque lot a un coût fixe.

Le garde-fou n'a jamais été déclenché : la mémoire disponible n'est pas descendue sous 2,6 Go.

### Extrapolation au volume complet

On multiplie le nombre de caractères réellement présents dans les fichiers préparés par le débit mesuré pour chaque langue. Le temps de chargement des modèles (moins d'une minute en tout) est négligeable.

| Jeu | Tickets | Caractères | Largeur 2 | Largeur 4 |
|---|---|---|---|---|
| Tobi-Bueck (entraînement) | 3 600 | 1,53 million | environ 66 min | environ 83 min |
| tasksource (test externe) | 473 | 0,10 million | environ 5 min | environ 6 min |
| decisionmodelhub (complément) | 800 | 0,30 million | environ 10 min | environ 16 min |
| **Total** | **4 873** | **1,93 million** | **environ 1 h 20** | **environ 1 h 45** |

**Réserves** : mesure sur 50 tickets seulement ; poste chargé, donc les temps peuvent varier ; les débits de l'allemand, de l'espagnol et du portugais pour tasksource sont incertains ; le débit de l'anglais sur les cas d'urgence est supposé égal à celui de Tobi-Bueck (**non mesuré**). Le « complément » éventuel au-delà de ces trois jeux n'est pas compté.

### Tailles à télécharger

| Élément | Taille |
|---|---|
| Modèles anglais, allemand et espagnol | environ 0,9 Go |
| Modèle multilingue (portugais) | environ 0,9 Go |
| Jeu Tobi-Bueck (fichier CSV utilisé) | 26 Mo (le dépôt contient aussi deux autres fichiers, 8 et 19 Mo, non utilisés) |
| tasksource, partie test | 40 Ko |
| decisionmodelhub, deux fichiers | 0,8 Mo |
| **Total** | **environ 1,9 Go** |

À cela s'ajoute l'environnement Python du groupe `translate` : environ 800 Mo sur disque une fois installé (mesure faite sous Windows, dossier `.venv` complet, outils de développement compris).

## Qualité de la traduction

Les extraits ci-dessous sont courts et cités avec l'attribution des auteurs (voir la section suivante).

| Langue | Original | Traduction |
|---|---|---|
| Anglais (Tobi-Bueck) | An unexpected software crash occurred while running data analytics in KNIME, likely due to conflicting updates. | Un crash logiciel inattendu s'est produit lors de l'exécution de l'analyse des données dans KNIME, probablement en raison de mises à jour contradictoires. |
| Allemand (Tobi-Bueck) | Das Anwendungsprogramm für Datenanalyse hat vorübergehende Stürze. | Le programme d'analyse des données a des chutes temporaires. |

**Constats sur l'échantillon** (relus par l'agent de développement, pas encore par le développeur) :

- Le français est fluide et le sens est conservé sur les tickets courants.
- Les termes techniques sont parfois mal rendus : « Stürze » (plantages) devient « chutes » ; « Light User » devient « Utilisateur de lumière » ; « File Share » devient « part de fichier » ou « actions de fichiers » ; « Active Directory » devient « Annuaire actif ».
- Les noms de produits sont en général conservés (KNIME, HubSpot, Ubuntu).
- Les tickets très courts, ou mélangeant deux langues (anglais dans une phrase portugaise, par exemple), sont les moins fiables.
- Ces erreurs sont acceptables pour entraîner un classifieur (le sujet du ticket reste reconnaissable), mais **pas pour montrer des tickets « réels » au jury sans relecture** : les 50 tickets de référence relus par le développeur restent nécessaires.

## Correspondance des étiquettes d'origine vers la taxonomie

> **Proposition à valider par le développeur.** C'est une décision ouverte de l'Issue #29. Les règles sont dans `config/public_label_mapping.yaml`, appliquées à l'échantillon pour juger de leur effet. Les étiquettes d'origine sont toujours conservées à côté.

### tasksource (étiquette d'origine : une classe sur sept)

| Classe d'origine | Catégorie proposée | Tickets | Doute |
|---|---|---|---|
| Active Directory | `accounts` | 41 | Non |
| Computer-Services | `workstation` | 34 | Oui : la classe mélange des demandes variées |
| Fileservice | `infrastructure` | 119 | Oui : beaucoup de « File Share Access », qui ressemblent à des demandes de droits (`accounts`) |
| O365 | `messaging` | 73 | Non |
| Software | `software` | 50 | Non |
| EOL | aucune | (compté avec les suivants) | Le sens exact de la classe n'est pas expliqué sur les pages lues. Les exemples vus sont des tickets automatiques « système à mettre en fin de vie » (`infrastructure` possible). |
| Support general | aucune | 156 au total pour EOL et Support general | Classe trop vague |

Le jeu n'a ni priorité ni type : ces étiquettes manquent.

### Tobi-Bueck (étiquette d'origine : file, type, priorité et mots-clés)

- **Type** : Incident et Problem donnent `incident` (Problem est à confirmer) ; Request et Change donnent `service_request`. **Rien ne donne `information`** : cette classe n'existe pas dans ce jeu.
- **Priorité** : low devient P4, medium devient P3, high devient P2. Le jeu n'a pas de niveau critique, donc **P1 n'est jamais proposé**. Or 57 % des tickets des files informatiques sont « high » : la priorité d'origine est probablement trop haute pour notre échelle.
- **Catégorie** : règles ordonnées sur les mots-clés (tags) et sur le sujet ; la première qui correspond l'emporte. Les mots-clés trop génériques (Tech Support, IT, Performance, Feedback…) ne servent jamais.

| Catégorie proposée | Tickets sur 3 600 |
|---|---|
| `security` | 911 |
| `software` | 793 |
| `network` | 560 |
| `infrastructure` | 371 (dont des cas douteux) |
| `workstation` | 164 |
| `accounts` | 30 |
| `messaging` | 11 |
| `printing` | 3 |
| `backup` | 3 |
| `telephony` | 1 |
| **Aucune catégorie** | **753** (21 %) |
| `procurement`, `admin_billing` | 0 (les files de facturation et d'achat ont été écartées) |

**Cas douteux et limites** :

- **Déséquilibre** : un quart des tickets est proposé en `security`, parce que le mot-clé « Security » est très répandu dans ce jeu synthétique, y compris pour des tickets qui parlent d'autre chose. À l'inverse, `printing`, `backup`, `telephony`, `messaging` et `accounts` ont presque aucun exemple. Le classifieur aura besoin du complément généré.
- **291 propositions marquées douteuses** : les mots-clés très généraux de pannes (Outage, Disruption, Recovery) sont rattachés à `infrastructure` par défaut.
- **Ordre des règles** : un ticket avec les mots-clés Security et Backup est classé `security` (la première règle l'emporte), alors que `backup` serait parfois plus juste.
- **Les mots-clés ne sont pas fiables** (jeu synthétique, étiquettes générées). Une relecture d'un échantillon par le développeur est nécessaire avant de s'en servir pour l'entraînement.
- **Aucun ticket ne se rattache à** `procurement` et `admin_billing` dans la part informatique de ce jeu : ces catégories viendront des tickets générés.

Les 800 cas de decisionmodelhub n'ont pas de catégorie : leur étiquette (`expected`, urgent ou non) sert à la revue de priorité.

## Licences et attributions

| Jeu | Licence (relue sur la carte) | Auteur et source | Modifications apportées |
|---|---|---|---|
| customer-support-tickets | CC BY-NC 4.0 | Tobias Bueck, <https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets> | Sélection des files informatiques, correction de la langue, traduction automatique en français, étiquettes proposées pour notre taxonomie |
| it-support-tickets | CC BY 4.0 | Leonardo Santiago Benitez Pereira, « Classification of IT Support Tickets », Zenodo, 2022, DOI 10.5281/zenodo.7648117 (copie Hugging Face : tasksource), <https://huggingface.co/datasets/tasksource/it-support-tickets> | Suppression des doublons et du début répété par l'outil, traduction en français, étiquettes proposées |
| support-urgency | CC BY 4.0 | decisionmodelhub, <https://huggingface.co/datasets/decisionmodelhub/support-urgency> | Traduction en français |

- Les modèles OPUS-MT sont sous licence Apache-2.0 (Helsinki-NLP, université d'Helsinki). Les traductions sont produites par ces modèles et peuvent contenir des erreurs : elles ne sont pas validées par les auteurs des jeux, qui n'approuvent pas ce projet.
- **CC BY-NC (Tobi-Bueck) interdit l'usage commercial** : si le projet devenait un produit, cette part du corpus ne pourrait plus servir. Le projet est pédagogique et non commercial.
- Aucune donnée traduite n'est versionnée dans le dépôt. Seuls quelques extraits courts figurent dans cette page, avec leur attribution.
- Les modèles de traduction ne sont pas non plus dans le dépôt : ils sont téléchargés dans le cache Hugging Face de l'utilisateur.

## Options pour la suite

Le développeur choisira. Chaque option a ses limites.

| Option | Avantages | Limites |
|---|---|---|
| **A. Poste local, tâche de nuit** | Simple, déjà prêt. Environ 1 h 20 à 1 h 45 selon la largeur du faisceau. `--resume` permet de reprendre après un arrêt. Aucune donnée ne quitte le poste. | Charge le poste pendant ce temps (environ un tiers du processeur, moins de 2 Go de mémoire). À planifier hors des heures de travail. |
| **B. Local en deux fois** (anglais d'abord, puis allemand et autres) | Permet d'entraîner une première version du classifieur plus tôt | Deux lancements à suivre |
| **C. Kaggle ou Colab** (notebook versionné, données publiques uniquement) | Libère le poste | Mise en place d'un notebook et d'un compte ; sessions limitées en durée ; reste sur CPU ou GPU gratuit selon la disponibilité. Le plan B de CLAUDE.md réserve ce recours aux données publiques : c'est le cas ici. |
| **D. Un seul jeu à la fois** (Tobi-Bueck d'abord, puis le reste) | Réduit le risque, résultats progressifs | Plus de suivi |

Au vu des mesures, **la charge sur le poste est modeste et le temps total court** : l'option A semble suffisante, mais cette page ne tranche pas. Avant tout lancement complet, le développeur doit aussi valider les règles de correspondance des étiquettes (elles ne changent pas la traduction, mais la sortie les contient).

À décider également : la largeur du faisceau (2 par défaut, 4 plus fidèle mais environ 15 à 40 % plus lent sur les mesures), et ce qu'on fait des 64 textes de tasksource dont la langue n'a pas pu être déterminée.

## Ce qui n'a pas été vérifié

- La traduction complète n'a pas été lancée : toutes les durées sont des extrapolations à partir de 50 tickets.
- La qualité de la traduction n'a été jugée que sur quelques extraits, sans score automatique (BLEU ou autre) ni relecture par le développeur.
- La précision de la détection de langue n'a pas été mesurée sur un échantillon relu.
- Le gain annoncé de CTranslate2 n'a pas été mesuré sur ce poste.
- Les tailles des modèles sont celles lues dans le cache après téléchargement, pas une somme officielle des fiches.
- Le sens de la classe « EOL » de tasksource reste à confirmer.

## Fichiers du projet liés à cette étape

| Fichier | Rôle |
|---|---|
| `config/public_datasets.yaml` | Jeux, licences attendues, filtres, graine, modèles de traduction |
| `config/public_label_mapping.yaml` | Proposition de correspondance des étiquettes |
| `src/data/public_datasets.py` | Licence, téléchargement, nettoyage, langue, échantillonnage, sauvegarde |
| `src/data/label_mapping.py` | Application des règles de correspondance |
| `src/data/translation.py` | Segmentation, balises, traducteur, garde-fou mémoire, mesure de la charge |
| `scripts/fetch_public_datasets.py`, `scripts/translate_public.py` | Points de lancement |
| `tests/test_public_datasets.py`, `tests/test_label_mapping.py`, `tests/test_translation.py` | Tests sans téléchargement ni modèle |

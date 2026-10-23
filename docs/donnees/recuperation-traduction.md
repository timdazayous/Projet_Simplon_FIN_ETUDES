# Récupération et traduction des jeux publics

**Issue** : #29 (phase 1 : script, échantillon, mesures ; phase 2 : étiquettes, exclusions, glossaire, répartition, commande de nuit) · **Compétences** : C1 (extraction depuis un fichier et un service web, filtrage, script structuré), C3 (homogénéisation de la langue et des formats, suppression des entrées corrompues) · **Date** : 21 octobre 2026 (phase 1), 23 octobre 2026 (phase 2)

Cette page décrit comment les jeux publics retenus dans l'[inventaire](jeux-publics.md) sont récupérés, nettoyés puis traduits en français. Elle contient aussi les **mesures réelles** de traduction sur le poste du développeur, les règles d'étiquetage décidées le 23 octobre, la répartition du corpus et la commande à lancer la nuit.

**Périmètre** : le script est écrit et testé, la traduction a été mesurée sur des échantillons de 50 tickets, et une traduction de contrôle de 16 tickets a vérifié le glossaire. **La traduction complète n'a pas été lancée** : une commande unique est prête (voir « Commande de nuit »), le développeur la lancera.

## Résumé

- Trois jeux sont récupérés depuis Hugging Face : un pour l'entraînement, un pour le test externe, un en complément pour la revue de priorité.
- La licence de chaque jeu est **vérifiée sur la carte Hugging Face avant tout téléchargement**. Si elle diffère de celle attendue, le script s'arrête.
- Après nettoyage, correspondance des étiquettes, plafonnement de `security` et tirage reproductible, il reste **7 682 tickets d'entraînement, 457 tickets de test externe et 800 cas d'urgence**. Décision du 2026-10-23 : on traduit les 7 682 tickets d'entraînement et l'on choisit la répartition **après** traduction (tirage au hasard ou limite par catégorie), sans avoir à retraduire.
- Décisions du 23 octobre appliquées : seuls les tickets rattachés à une catégorie sont gardés ; `security` est plafonné à 8 % ; les classes tasksource « Fileservice », « EOL » et « Support general » sont découpées par règles de mots-clés ; les 65 textes de langue indécidable sont écartés ; un glossaire protège les termes techniques pendant la traduction.
- Sur CPU, avec 4 threads, la traduction de 50 tickets prend **de 50 à 61 secondes** (environ une seconde par ticket). L'extrapolation donne **environ 3 h** au faisceau de 4 pour les quelque 8 940 tickets à traduire (environ 1 h 45 pour l'ancien tirage de 3 600). C'est bien moins que les « quelques heures » estimées dans l'inventaire.
- Le poste n'est pas saturé : le processus utilise environ un tiers du processeur et au plus 1,8 Go de mémoire.
- Le corpus public réel est très **déséquilibré** (rien pour `procurement` et `admin_billing`, très peu pour `printing`, `backup`, `telephony`, `messaging`) : le générateur doit produire environ **3 100 à 3 700 messages** au lieu des 2 400 prévus (voir « Répartition du corpus »).

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
uv run --group translate python scripts/translate_public.py --dataset customer_support --threads 4 --beams 4 --resume
```

| Option | Rôle |
|---|---|
| `--limit N` | Ne traduit que N tickets, répartis entre les langues présentes (tirage à graine fixe) |
| `--threads N` | Nombre de threads de calcul de torch (4 par défaut, pour laisser de la place au reste du poste) |
| `--batch-size N` | Nombre de segments traduits ensemble (8 par défaut) |
| `--beams N` | Largeur de la recherche en faisceau : 1 est plus rapide, 4 est plus fidèle (2 par défaut) |
| `--min-ram-mb N` | Seuil du garde-fou mémoire (1 500 Mo par défaut) |
| `--resume` | Reprend après un arrêt, sans retraduire les tickets déjà faits |
| `--glossary FICHIER` / `--no-glossary` | Glossaire de termes protégés (`config/translation_glossary.yaml` par défaut), ou traduction sans glossaire pour comparer |

Pour tout faire en une seule commande (préparation, puis traduction des trois jeux), voir « Commande de nuit ».

Toute la configuration (jeux, licences attendues, graine, modèles, plafond de `security`) est dans `config/public_datasets.yaml`.

**Où vont les fichiers.** Par défaut dans `data/raw/public/` (ignoré par Git). Sous Windows, le dossier du dépôt peut être trop profond pour supprimer ensuite un worktree : la variable d'environnement `PUBLIC_DATA_DIR` déplace les fichiers de sortie et le cache de téléchargement ailleurs (par exemple `PUBLIC_DATA_DIR=C:/Users/<nom>/data-public`). Les modèles de traduction restent dans le cache Hugging Face de l'utilisateur.

## Ce que fait le script de récupération

| Étape | Détail |
|---|---|
| Initialisation | Lecture de `config/public_datasets.yaml` et de la proposition de correspondance des étiquettes. Un nom de jeu inconnu arrête le script avec un message clair. |
| Vérification de la licence | La licence lue sur la carte du jeu doit être celle attendue (`cc-by-nc-4.0` ou `cc-by-4.0`). Sinon : refus avant tout téléchargement, code de sortie 3. |
| Téléchargement | Via `huggingface_hub`, avec un cache local dans `data/raw/public/_hf_cache/` (ignoré par Git). Une erreur réseau ou de format sur un jeu est signalée sans effacer ce qui est déjà enregistré pour les autres. |
| Nettoyage et filtrage | Voir le tableau suivant. |
| Étiquettes et exclusions | Les étiquettes d'origine sont conservées telles quelles. Les étiquettes de notre taxonomie sont ajoutées à côté, avec **la règle appliquée** (champ `rule`). Un ticket sans catégorie est écarté (jeux d'entraînement et de test). |
| Plafond d'une catégorie | `security` est ramenée à 8 % du jeu d'entraînement par un tirage reproductible. |
| Échantillonnage | Tirage reproductible : même graine (42) et mêmes données donnent le même résultat. |
| Sauvegarde | Fichiers JSONL dans `data/raw/public/`, écrits de façon atomique (fichier temporaire puis renommage), plus un rapport `prepare_report.json` avec les comptes de chaque étape. |

Les fichiers de sortie sont dans `data/raw/public/`, un dossier **ignoré par Git** : aucun jeu de données n'entre dans le dépôt.

### Choix de nettoyage

Le premier motif rencontré l'emporte : chaque ligne écartée est comptée une seule fois.

Chiffres de la phase 2, mesurés le 23 octobre 2026 sur les fichiers réels. Les lignes sont dans l'ordre d'application.

| Règle | Pourquoi | Tobi-Bueck | tasksource | urgence |
|---|---|---|---|---|
| Lignes lues | | 28 587 | 657 | 800 |
| Files non informatiques écartées (Customer Service, Billing, Sales…) | Hors sujet pour un MSP. Seules Technical Support, IT Support et Service Outages and Maintenance sont gardées. | 15 644 | sans objet | sans objet |
| Ligne illisible (étiquette absente ou hors des classes) | Impossible à relier à une étiquette d'origine | 0 | 0 | 0 |
| Texte vide | Rien à classer | 0 | 0 | 0 |
| Texte corrompu (caractères de remplacement `U+FFFD`, accents mal encodés) | Le modèle de traduction recopierait les erreurs | 0 | 2 | 0 |
| Texte trop court (moins de 20 ou 10 caractères selon le jeu) | Pas assez de contenu | 0 | 12 | 0 |
| Texte trop long (plus de 4 000 caractères) | Rare, coûteux à traduire, souvent du bruit | 0 | 0 | 0 |
| **Langue indécidable** (`language_undecidable`) | Texte trop court ou ambigu : on ne devine pas (décision du 23 octobre) | 0 | 65 | 0 |
| Langue décidée mais absente de la liste du jeu (`language_unsupported`) | Pas de modèle de traduction | 0 | 0 | 0 |
| Doublon exact (casse et espaces ignorés) | Évite de compter deux fois le même ticket, et une fuite entre entraînement et test | 1 | 112 | 0 |
| **Gardés après nettoyage** | | **12 942** | **466** | **800** |
| **Sans catégorie** (`no_category`) | Décision du 23 octobre : seuls les tickets rattachés à une catégorie servent | 2 656 | 0 | sans objet |
| **Trop flou** (`support_general_unclear`) | Classe « Support general » : ce que les règles de mots-clés ne tranchent pas | sans objet | 9 | sans objet |
| **Gardés après étiquetage** | | **10 286** | **457** | **800** |
| **Plafond de `security`** (`capped`) | Le mot-clé « Security » est omniprésent : 3 218 tickets, ramenés à 614 (8 %) par tirage à graine fixe | 2 604 | 0 | 0 |
| **Gardés après plafond** | | **7 682** | **457** | **800** |
| **Gardés après tirage** (plafond global de 3 600 pour l'entraînement) | Taille du corpus public prévue (60 % de 6 000) | **3 600** | **457** | **800** |

Remarque : par rapport à la phase 1 (473 tickets de test, 64 textes de langue indécidable, 106 doublons), le retrait de deux débuts répétés de plus (« New information received on closed ticket », « Reminder of paused Support Ticket ») fait apparaître 6 doublons de plus et un texte de langue indécidable de plus.

Autres opérations d'homogénéisation, appliquées à tous les textes :

- normalisation Unicode (NFC), retours à la ligne unifiés, espaces insécables et espaces multiples ramenés à un espace, caractères de contrôle supprimés ;
- le CSV de Tobi-Bueck contient des `\n` écrits en toutes lettres (barre oblique inversée suivie de la lettre n) : ils sont remplacés par de vrais retours à la ligne ;
- dans tasksource, le début répété par l'outil de ticketing (« [TICKET ID] - New Support Ticket received - ») est retiré, car il ne porte aucune information ;
- un seul fichier est utilisé pour Tobi-Bueck : la nouvelle version du jeu (28 587 lignes). L'ancienne version (20 000 lignes) en est en grande partie un sous-ensemble.

### Constats sur les données

Ces constats viennent de l'ouverture réelle des fichiers, ce que l'inventaire n'avait pas fait.

- **La langue annoncée est parfois fausse.** Dans les files informatiques de Tobi-Bueck, **1 602 tickets déclarés « de » (allemand) sont écrits en anglais**, soit près de 30 % des 5 600 tickets déclarés allemands. Les traduire avec le modèle allemand les laisse presque inchangés (constaté sur un premier échantillon). Le script détecte la langue sur le texte et **corrige** l'étiquette de langue (1 603 corrections au total, comptées dans le rapport sous `language_corrected`). Après correction, l'échantillon de 3 600 tickets de la phase 2 contient 2 535 tickets anglais et 1 065 allemands.
- **Le contenu de Tobi-Bueck est peu « MSP ».** Les tickets sont synthétiques et parlent souvent de marketing, de santé ou de plateformes SaaS, avec des étiquettes (tags) aléatoires. Le jeu sert à apprendre la forme d'un ticket, pas le métier d'un MSP : les 40 % de tickets générés par le projet restent indispensables.
- **tasksource contient beaucoup de quasi-doublons** (tickets automatiques identiques à un numéro près) : 112 doublons exacts sur 657 une fois les balises et les débuts répétés ignorés.
- **Des alertes de supervision** (check_mk, ping) sont mélangées aux tickets de tasksource. Elles sont conservées, avec leurs étiquettes d'origine.

La langue de tasksource est détectée par une méthode volontairement simple (mots courants et lettres distinctives, sans bibliothèque ajoutée). Elle est testée sur des exemples, mais **sa précision n'a pas été mesurée sur un échantillon relu à la main**. Les 65 textes trop courts ou ambigus sont écartés (compteur `language_undecidable`) plutôt que devinés.

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
| `proposed_labels` | Catégorie, type et priorité proposés, **règle utilisée** (`rule`, par exemple `Fileservice:fileshare_access`), indicateur de doute (`doubtful`) |
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
| Glossaire de termes techniques protégés par le même mécanisme de code (voir plus bas) | Le modèle traduit à tort « Light User » ou « File Share ». Le glossaire est un fichier de configuration, modifiable sans toucher au code. | Corriger après coup dans le texte traduit : impossible de savoir quelle traduction était juste |
| 4 threads de calcul, lots de 8 segments. Largeur de faisceau 2 par défaut, **4 pour la commande de nuit** | Laisse de la place au reste du poste. La traduction de nuit n'est pas pressée : largeur 4, plus fidèle, coûte environ 15 à 40 % de temps en plus (voir mesures). | Tous les cœurs : poste déjà chargé |
| Un seul modèle en mémoire à la fois, tickets traités langue par langue | Limite la mémoire (au plus 1,8 Go pour le modèle portugais) | Tous les modèles chargés ensemble |
| Écriture de la sortie par petits groupes de 10 tickets, option `--resume` | Un arrêt (garde-fou, veille, coupure) ne fait rien perdre | Écrire à la fin seulement |
| Sans bibliothèque d'optimisation (CTranslate2) pour l'instant | Une dépendance et une étape de conversion de moins. À reconsidérer seulement si le temps mesuré est un problème, ce qui n'est pas le cas. | CTranslate2 (annoncé 3 à 4 fois plus rapide dans son propre banc d'essai, **non mesuré ici**) |

### Garde-fou mémoire

Avant chaque lot, le script lit la mémoire disponible du système. Si elle passe **sous 1 500 Mo**, il s'arrête proprement : ce qui est déjà traduit est enregistré, le rapport indique `stopped_low_memory`, et le code de sortie est 4. Le même contrôle est fait avant et après le chargement d'un modèle. Le seuil se change avec `--min-ram-mb`. Le comportement est testé avec une mémoire simulée.

### Glossaire de termes protégés

Le modèle OPUS-MT traduit mot à mot les termes techniques qui sont des noms propres ou du jargon. Le glossaire, dans `config/translation_glossary.yaml`, liste les termes à ne pas traduire. Il fonctionne comme les balises `[NAME]` : avant la traduction, chaque terme est remplacé par un code opaque (`ZZ900ZZ` à `ZZ999ZZ`, une plage distincte de celle des balises) ; après la traduction, le code est remplacé par le terme.

| Champ du fichier | Rôle |
|---|---|
| `term` | Le terme tel qu'il est écrit dans les tickets, mot entier (« VPN » ne protège pas « VPNs ») |
| `fr` | Facultatif : une formulation française imposée (par exemple « File Share Access » devient « Accès à un partage de fichiers ») ; sinon le terme est restitué tel quel |
| `ignore_case` | Facultatif : ignore la casse. Désactivé par défaut pour les mots courants (« Teams », « Exchange ») : « our teams » n'est pas protégé |

Le fichier contient environ 45 termes : annuaire et comptes (Active Directory, Light User, Basis User), partages de fichiers (File Share, File Share Access, avec leur formulation française), Microsoft et messagerie (Office 365, O365, Microsoft 365, Outlook, Teams, SharePoint, OneDrive, Exchange, Skype, Intune, Azure, BitLocker, Windows), accès distant et réseau (VPN, Citrix, TeamViewer, Nexthink, Wi-Fi, DHCP, DNS, LDAP, SSO, MFA), mobiles (BlackBerry, iPhone, iPad) et quelques technologies fréquentes dans Tobi-Bueck (SaaS, API, Kubernetes, PostgreSQL, Redis, ClickUp). Ils ont été choisis en comptant les mots en majuscule les plus fréquents dans les fichiers préparés.

**Termes essayés puis retirés** : « Leaving Employee » et « Service Portal ». Sur la traduction de contrôle, « Employé sortant » (traduction du modèle pour « Leaving Employee ») était correcte : la protéger la dégradait.

Limites : un code abîmé par le modèle est signalé (`tag_not_restored`), mais un code **supprimé** par le modèle ferait perdre le terme sans alerte (non observé sur la traduction de contrôle). Un terme au pluriel ou avec une faute de frappe n'est pas reconnu. Le glossaire compte au plus 100 termes (limite de la plage de codes).

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

Ce tableau date de la phase 1 : en phase 2, tasksource compte 457 tickets au lieu de 473 (écart négligeable sur le temps) et Tobi-Bueck 3 600 tickets de contenu différent (même nombre, caractères non recomptés).

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

### Effet du glossaire (traduction de contrôle du 23 octobre)

**Méthode** : 16 tickets distincts de tasksource en anglais (au plus 30 autorisés, en deux petites séries), choisis parce qu'ils contiennent les termes visés, traduits deux fois avec le même modèle (anglais vers français), 4 threads, faisceau 4 : une fois sans glossaire, une fois avec. Un seul processus lourd à la fois, mémoire libre toujours au-dessus du seuil de 1 500 Mo. Extraits courts, source : tasksource (CC BY 4.0).

| Original | Sans glossaire | Avec glossaire |
|---|---|---|
| Light User for external … Create Light user for | Utilisateur de lumière pour l'extérieur … Créer l'utilisateur de lumière pour | Light User pour externe … Créer Light User pour |
| Basis User … Create Windows account for internal user | Utilisateur de base … Base Utilisateur Créer un compte Windows | Basis User … Créer un compte Windows |
| File Share Access … Grant access to file share … Read / Write File Share | Accès au partage de fichiers … Déposer Partager Accès Accorder un accès au partage de fichier … Lire / écrire le fichier Partager | Accès à un partage de fichiers … Accorder l'accès à un partage de fichiers … Lire / écrire Partage de fichiers |
| outlook not working | perspectives qui ne fonctionnent pas | Outlook ne travaillant pas |

**Lecture** : deux des trois erreurs citées par la phase 1 sont corrigées, « Light User » (« Utilisateur de lumière ») et « File Share » (« part de fichier », « Déposer Partager »). « Basis User » devenait « Utilisateur de base » ou « Base Utilisateur » (incohérent d'un segment à l'autre) et reste maintenant constant. « Outlook » n'est plus pris pour « perspectives ».

**Ce qui n'a pas pu être reproduit** : « Active Directory » devenant « Annuaire actif » (constat de la phase 1). Sur les deux tickets de contrôle qui contiennent ce terme, le modèle le laissait déjà intact avec et sans glossaire ; le glossaire garantit seulement qu'il le restera. Le résultat n'est pas parfait : « Outlook ne travaillant pas » reste maladroit, car le glossaire protège un terme mais ne corrige pas la grammaire autour. Aucun score automatique n'a été calculé.

## Correspondance des étiquettes d'origine vers la taxonomie

> **Règles décidées par le développeur le 23 octobre 2026** (commentaire de l'Issue #29), mises en œuvre dans `config/public_label_mapping.yaml`. Les règles sont des **données de configuration** (expressions régulières par classe), pas du code. Pour chaque ticket, la règle appliquée est enregistrée (`proposed_labels.rule`) et les cas fragiles sont marqués (`doubtful`). Les étiquettes d'origine sont toujours conservées à côté. **Les règles de mots-clés n'ont pas été relues sur un échantillon par le développeur** : elles ont été vérifiées à la main sur la liste complète des tickets « Support general », « EOL » et « Fileservice » (moins de 300 lignes, très répétitives), pas sur un échantillon tiré au hasard.

### tasksource : règles par classe

Les règles s'appliquent au sujet et au corps, **balises de masquage retirées** (sinon `[SERVER]` déclenche la règle « serveur »). La première règle qui correspond l'emporte.

| Classe d'origine | Règle | Catégorie | Type | Tickets |
|---|---|---|---|---|
| Active Directory | classe entière | `accounts` | non fourni | 41 |
| Computer-Services | classe entière (douteux : la classe mélange des demandes variées) | `workstation` | non fourni | 34 |
| O365 | classe entière | `messaging` | non fourni | 73 |
| Software | classe entière | `software` | non fourni | 50 |
| Fileservice | `fileshare_access` : « File Share Access », « Remove File Share Access » (accès à un partage) | `accounts` | `service_request` | 97 |
| Fileservice | `fileshare_access_free_text` : demande de droits écrite librement (« grant access », « access to », « permission », « acesso », « Zugriffsrechte »…), douteux | `accounts` | `service_request` | 15 |
| Fileservice | `fileservice_other` : tout le reste (dossier manquant, lecteur réseau inaccessible) | `infrastructure` | non fourni | 7 |
| EOL | `eol_workstation` : poste, portable (aucun cas dans les données) | `workstation` | `service_request` (priorité P4) | 0 |
| EOL | `eol_server` : serveur, par défaut | `infrastructure` | `service_request` (priorité P4) | 2 |
| Support general | `account_lifecycle` : « Basis User », « Light User », « Create Windows account », « Leaving Employee » | `accounts` | `service_request` | 78 |
| Support general | `vulnerability_notice` : « Vulnerable … on [SERVER] », « Security Tools » (douteux : c'est une mise à jour corrective) | `security` | non fourni | 9 |
| Support general | `mobile_phone` : téléphones, BlackBerry, iPhone, iPad, « celular », « teléfono » | `telephony` | non fourni | 26 |
| Support general | `network_access` : VPN, Internet, Wi-Fi, DHCP, DNS | `network` | non fourni | 13 |
| Support general | `credentials` : mot de passe, « senha », « anmelden » | `accounts` | non fourni | 2 |
| Support general | `server_work` : mises à jour d'OS, serveur, VM | `infrastructure` | non fourni | 4 |
| Support general | `workstation_hardware` : portable, « equipo no inicia », « duplicação de tela » | `workstation` | non fourni | 3 |
| Support general | `software_install` : installation, applications (douteux) | `software` | non fourni | 3 |
| Support general | **`still_vague` : ce qui reste** | **exclu** | | **9 exclus** |

Les neuf tickets exclus (`support_general_unclear`) sont par exemple « Alteração de Aprovação », « Erro no site da RFB », « Sem icone do Service Portal », « Can not connect to [URL] », « activacion equipo ». L'ordre compte : un modèle de création de compte qui mentionne un téléphone reste `accounts`.

Le jeu n'a ni priorité ni type par défaut : seules les règles ci-dessus en donnent (type `service_request` pour les demandes de droits et les créations de comptes, P4 pour la fin de vie).

**Effet sur le jeu de test** (457 tickets) :

| Catégorie | Avant (phase 1, 473 tickets) | Après (phase 2, 457 tickets) |
|---|---|---|
| `accounts` | 41 | 233 |
| `messaging` | 73 | 73 |
| `workstation` | 34 | 37 |
| `software` | 50 | 53 |
| `telephony` | 0 | 26 |
| `network` | 0 | 13 |
| `infrastructure` | 119 | 13 |
| `security` | 0 | 9 |
| aucune (écartés ou sans catégorie) | 156 | 0 (9 exclus) |
| `printing`, `backup`, `procurement`, `admin_billing` | 0 | 0 |

Limites du jeu de test : plus de la moitié (233 sur 457) est en `accounts`, surtout des **modèles de tickets quasi identiques** (créations de comptes et accès aux partages, qui ne diffèrent que par un nom). Les scores sur `accounts` seront donc optimistes. `printing`, `backup`, `procurement` et `admin_billing` n'ont **aucun** ticket de test : il faudra les couvrir avec les 50 tickets relus par le développeur et le générateur.

### Tobi-Bueck : étiquettes, filtre et plafond

- **Type** : Incident et Problem donnent `incident` (Problem est à confirmer) ; Request et Change donnent `service_request`. **Rien ne donne `information`** : cette classe n'existe pas dans ce jeu.
- **Priorité** : low devient P4, medium devient P3, high devient P2. Le jeu n'a pas de niveau critique, donc **P1 n'est jamais proposé**. Or 57 % des tickets des files informatiques sont « high » : la priorité d'origine est probablement trop haute pour notre échelle.
- **Catégorie** : règles ordonnées sur les mots-clés (tags) et sur le sujet ; la première qui correspond l'emporte. Les mots-clés trop génériques (Tech Support, IT, Performance, Feedback…) ne servent jamais. Règles inchangées depuis la phase 1.
- **Filtre (décision du 23 octobre)** : un ticket sans catégorie est écarté (2 656 sur 12 942, soit 21 %).
- **Plafond de `security`** : le mot-clé « Security » est omniprésent dans ce jeu synthétique (3 218 tickets rattachés). `security` est ramenée à **8 %** de l'ensemble gardé, par un tirage reproductible (graine 42 et nom de la catégorie), soit 614 tickets. Le paramètre est `category_shares` dans `config/public_datasets.yaml` ; 8 % correspond au poids de `security` dans `config/generator.yaml` (8 sur 102, soit 7,8 %), et un test vérifie que les deux restent proches. Le calcul : pour `n` tickets des autres catégories, on garde au plus `0,08 / 0,92 × n` tickets de `security`.

| Catégorie | Après filtre, avant plafond | Après plafond | Dans les 3 600 tirés |
|---|---|---|---|
| `software` | 2 977 | 2 977 | 1 358 |
| `network` | 1 979 | 1 979 | 938 |
| `infrastructure` | 1 347 | 1 347 | 629 |
| `security` | 3 218 | 614 | 307 |
| `workstation` | 568 | 568 | 268 |
| `accounts` | 137 | 137 | 70 |
| `messaging` | 33 | 33 | 17 |
| `printing` | 12 | 12 | 4 |
| `backup` | 8 | 8 | 7 |
| `telephony` | 7 | 7 | 2 |
| `procurement`, `admin_billing` | 0 | 0 | 0 |
| **Total** | **10 286** | **7 682** | **3 600** |

Avant (phase 1, sur les 3 600 tirés sans filtre) : `security` 911, `software` 793, `network` 560, `infrastructure` 371, `workstation` 164, `accounts` 30, `messaging` 11, `printing` 3, `backup` 3, `telephony` 1, et 753 sans catégorie.

**Cas douteux et limites** :

- **Le tirage de 3 600 coupe aussi les catégories rares** : sur les 7 682 tickets disponibles, le tirage garde environ 47 % de chaque catégorie, y compris `accounts` (137 devient 70), `messaging` (33 devient 17), `printing` (12 devient 4) et `telephony` (7 devient 2), alors qu'on manque d'exemples. Voir la décision proposée dans la section suivante.
- **Déséquilibre persistant** : `printing`, `backup`, `telephony`, `messaging` et `accounts` ont très peu d'exemples réels, `procurement` et `admin_billing` aucun. Le classifieur dépend du générateur pour ces catégories.
- **493 propositions marquées douteuses** (sur les 3 600 tirés) : surtout les mots-clés très généraux de pannes (Outage, Disruption, Recovery), rattachés à `infrastructure` par défaut.
- **Ordre des règles** : un ticket avec les mots-clés Security et Backup est classé `security` (la première règle l'emporte), alors que `backup` serait parfois plus juste.
- **Les mots-clés ne sont pas fiables** (jeu synthétique, étiquettes générées). Une relecture d'un échantillon par le développeur est nécessaire avant de s'en servir pour l'entraînement.

Les 800 cas de decisionmodelhub n'ont pas de catégorie : leur étiquette (`expected`, urgent ou non) sert à la revue de priorité.

## Répartition du corpus

Objectif du plan : environ **6 000 messages d'entraînement** (60 % publics traduits, 40 % générés), plus un test externe et un complément pour l'urgence. Les volumes ci-dessous sont **réels**, mesurés le 23 octobre 2026 après filtrage et plafonnement. `config/generator.yaml` n'a **pas** été modifié : cette section présente le besoin, le développeur décidera de l'ajustement.

### Ce que le corpus public fournit

| Jeu | Rôle | Volume |
|---|---|---|
| Tobi-Bueck | Entraînement | 7 682 disponibles, **3 600 tirés** (plafond de configuration) |
| tasksource | Test externe | 457 tickets (jamais dans l'entraînement) |
| decisionmodelhub | Revue de priorité (urgent ou non) | 800 cas, sans catégorie |

Détail par catégorie : voir les deux tableaux des sections précédentes.

### Besoin du générateur par catégorie

La cible est répartie comme les poids du générateur (`config/generator.yaml`, 102 au total) : par exemple 706 messages pour `messaging` (12 sur 102 de 6 000). Le besoin est la cible moins ce que fournit le corpus public. Le générateur produit aujourd'hui 2 400 messages de texte libre, avec ces mêmes poids (colonne « Actuel »).

| Catégorie | Cible sur 6 000 | Public tiré (3 600) | Besoin du générateur | Actuel (2 400) |
|---|---|---|---|---|
| `network` | 588 | 938 | 0 (public en excès de 350) | 235 |
| `messaging` | 706 | 17 | 689 | 282 |
| `workstation` | 706 | 268 | 438 | 282 |
| `software` | 588 | 1 358 | 0 (public en excès de 770) | 235 |
| `accounts` | 706 | 70 | 636 | 282 |
| `printing` | 412 | 4 | 408 | 165 |
| `infrastructure` | 471 | 629 | 0 (public en excès de 158) | 188 |
| `backup` | 353 | 7 | 346 | 141 |
| `security` | 471 | 307 | 164 | 188 |
| `telephony` | 412 | 2 | 410 | 165 |
| `procurement` | 294 | 0 | 294 | 118 |
| `admin_billing` | 294 | 0 | 294 | 118 |
| **Total** | **6 000** | **3 600** | **3 678** | **2 400** |

Avec le tirage actuel, le besoin total (3 678) dépasse l'écart « 6 000 moins 3 600 » (2 400), parce que `software`, `network` et `infrastructure` sont en excès dans le public : le corpus final compterait **7 278 messages**, dont **51 % générés** (au lieu de 40 %), et resterait déséquilibré vers `software`. Les besoins sont des totaux par catégorie : `generator.yaml` règle les poids **par canal**, pas par catégorie, donc le réglage exact reste à faire.

### Décision proposée : limiter le public par catégorie

Plutôt qu'un tirage au hasard de 3 600, on pourrait **garder tout le public rare et limiter chaque catégorie à sa cible** (`public = min(disponible, cible)`). Chiffres calculés sur les 7 682 tickets disponibles :

| Catégorie | Public gardé | Besoin du générateur |
|---|---|---|
| `network` | 588 | 0 |
| `messaging` | 33 | 673 |
| `workstation` | 568 | 138 |
| `software` | 588 | 0 |
| `accounts` | 137 | 569 |
| `printing` | 12 | 400 |
| `infrastructure` | 471 | 0 |
| `backup` | 8 | 345 |
| `security` | 471 | 0 |
| `telephony` | 7 | 405 |
| `procurement` | 0 | 294 |
| `admin_billing` | 0 | 294 |
| **Total** | **2 883** | **3 118** |

Le corpus fait alors 6 001 messages, parfaitement équilibré, mais **52 % générés** : plus de la moitié du corpus d'entraînement serait synthétique, ce qui limite la valeur du « corpus public traduit » devant le jury. Cette option n'est **pas mise en œuvre** (elle demande une petite évolution du script) : à décider avec le développeur. Dans les deux cas, la part générée augmente nettement, comme prévu.

## Commande de nuit

Une seule commande, un seul processus, qui prépare puis traduit les trois jeux (faisceau 4, 4 threads, lots de 8, glossaire, garde-fou mémoire, reprise automatique) :

```
uv sync --group dev --group translate
uv run --group translate python scripts/translate_all.py | Tee-Object -FilePath translate_all.log
```

Ce que fait `scripts/translate_all.py` :

1. Il prépare les jeux (licence vérifiée avant téléchargement, nettoyage, étiquettes, plafond) **si les fichiers préparés n'existent pas** ; `--refresh` force la préparation.
2. Il traduit dans l'ordre : Tobi-Bueck (anglais puis allemand), tasksource, decisionmodelhub. Le corpus d'entraînement passe en premier, pour qu'un arrêt en perde le moins.
3. **`--resume` est actif par défaut** : les tickets déjà traduits sont ignorés. Après un arrêt (garde-fou, coupure), **relancer la même commande** reprend où elle s'était arrêtée. `--no-resume` recommence de zéro.
4. Le garde-fou mémoire arrête proprement sous 1 500 Mo de mémoire disponible (`--min-ram-mb`).

| Code de sortie | Sens |
|---|---|
| 0 | Tout est traduit |
| 1 | Un téléchargement a échoué |
| 3 | Licence refusée : rien n'est téléchargé |
| 4 | Arrêt par le garde-fou mémoire : relancer la même commande quand la mémoire est libre |

**Avant de lancer** :

- Libérer de la mémoire : le modèle portugais (72 tickets de tasksource) monte à environ 1,8 Go, donc le garde-fou demande environ **3,3 Go libres** au départ. Le 23 octobre, il restait environ 2 Go libres avec le navigateur, Discord et l'éditeur ouverts : le lancement s'arrêterait sur le portugais (le reste serait traduit, la reprise couvrirait la fin).
- Empêcher la mise en veille de l'ordinateur et le laisser branché.
- Prévoir **environ 3 h** (7 682 tickets Tobi-Bueck, soit environ 2 h 40, plus 6 minutes pour tasksource et 16 pour decisionmodelhub ; l'ancien tirage de 3 600 prenait 83 minutes pour Tobi-Bueck), d'après les mesures de la phase 1 en faisceau 4 (le glossaire ajoute un coût négligeable mais **non mesuré** sur le volume complet). Compter jusqu'à 2 h 30 si le poste est chargé.
- Le téléchargement est inclus dans la première exécution : environ 27 Mo de jeux, et jusqu'à 1,9 Go de modèles s'ils ne sont pas déjà dans le cache Hugging Face.

**Après** : les fichiers `*_fr.jsonl` et les rapports `*_translation_report.json` (durées, mémoire, processeur, drapeaux `tag_not_restored`) sont dans le dossier de sortie. Vérifier qu'aucun processus Python de traduction ne reste actif.

Si la mémoire manque, la même traduction peut être lancée jeu par jeu (`translate_public.py --dataset … --beams 4 --resume`, voir « Commandes »).

## Licences et attributions

| Jeu | Licence (relue sur la carte) | Auteur et source | Modifications apportées |
|---|---|---|---|
| customer-support-tickets | CC BY-NC 4.0 | Tobias Bueck, <https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets> | Sélection des files informatiques, correction de la langue, traduction automatique en français, étiquettes proposées pour notre taxonomie |
| it-support-tickets | CC BY 4.0 | Leonardo Santiago Benitez Pereira, « Classification of IT Support Tickets », Zenodo, 2022, DOI 10.5281/zenodo.7648117 (copie Hugging Face : tasksource), <https://huggingface.co/datasets/tasksource/it-support-tickets> | Suppression des doublons et du début répété par l'outil, écart des textes de langue indécidable et des tickets trop vagues, traduction en français, étiquettes proposées |
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

**Décidé le 23 octobre 2026** : option A (traduction complète en local, de nuit), faisceau de 4, 65 textes de langue indécidable écartés. La commande est décrite dans « Commande de nuit ».

**Reste à décider, après traduction** : la répartition de l'entraînement (tirage au hasard, ou public limité par catégorie, voir « Répartition du corpus »), et l'ajustement de `config/generator.yaml` qui en découle. Les quatre catégories absentes du test externe (`printing`, `backup`, `procurement`, `admin_billing`) seront évaluées sur des tickets générés, résultat signalé comme optimiste (décision du 2026-10-23).

## Ce qui n'a pas été vérifié

- La traduction complète n'a pas été lancée : toutes les durées sont des extrapolations à partir de 50 tickets (phase 1). Le temps avec le glossaire sur le volume complet n'est pas mesuré.
- La qualité de la traduction n'a été jugée que sur quelques extraits, sans score automatique (BLEU ou autre) ni relecture par le développeur.
- L'effet du glossaire a été vu sur 16 tickets choisis pour contenir les termes visés : ce n'est pas une mesure sur un échantillon représentatif. Le cas « Active Directory » devenant « Annuaire actif » n'a pas été reproduit.
- Un code du glossaire **supprimé** par le modèle (et non abîmé) ne serait pas signalé.
- La précision de la détection de langue n'a pas été mesurée sur un échantillon relu.
- Les règles de mots-clés de tasksource ont été relues sur la liste complète des tickets concernés, mais pas par le développeur ; celles de Tobi-Bueck ne sont pas relues non plus.
- Le plafond de `security` (8 %) vient d'un tirage statistique : les tickets gardés ne sont pas relus.
- Le gain annoncé de CTranslate2 n'a pas été mesuré sur ce poste.
- Les tailles des modèles sont celles lues dans le cache après téléchargement, pas une somme officielle des fiches.
- Le sens de la classe « EOL » de tasksource reste à confirmer : les deux seuls tickets conservés sont des demandes automatiques de mise en fin de vie d'un serveur (règle appliquée : `infrastructure`, `service_request`, P4, décision du 23 octobre).

## Fichiers du projet liés à cette étape

| Fichier | Rôle |
|---|---|
| `config/public_datasets.yaml` | Jeux, licences attendues, filtres, plafond de `security`, graine, modèles de traduction |
| `config/public_label_mapping.yaml` | Correspondance des étiquettes (règles par classe et par mots-clés) |
| `config/translation_glossary.yaml` | Glossaire de termes protégés pendant la traduction |
| `src/data/public_datasets.py` | Licence, téléchargement, nettoyage, langue, exclusions, plafond, échantillonnage, sauvegarde |
| `src/data/label_mapping.py` | Application des règles de correspondance |
| `src/data/translation.py` | Segmentation, balises, glossaire, traducteur, garde-fou mémoire, mesure de la charge |
| `scripts/fetch_public_datasets.py`, `scripts/translate_public.py` | Récupération, et traduction d'un jeu |
| `scripts/translate_all.py` | Commande unique de nuit : préparation puis traduction des trois jeux |
| `tests/test_public_datasets.py`, `tests/test_label_mapping.py`, `tests/test_translation.py` | Tests sans téléchargement ni modèle |

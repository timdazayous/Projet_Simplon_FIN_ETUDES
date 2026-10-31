# Assemblage du corpus de classification

**Issue** : #46 · **Compétences** : C3 (agréger et homogénéiser des sources, jeux d'entraînement et de test sans fuite), C12 (jeux d'entraînement, de validation et de test distincts, évaluation fiable) · **Code** : `src/data/corpus.py`, `scripts/assemble_corpus.py` · **Configuration** : section `corpus` de `config/generator.yaml` · **Date** : 31 octobre 2026

Cette page décrit comment les tickets publics traduits et les tickets générés sont réunis en un corpus de classification : un jeu d'entraînement, un jeu de validation et deux jeux de test. Les volumes ci-dessous sont **réels** : ils viennent du rapport `report.json` produit par le script sur le poste du développeur (aucun texte de ticket n'est reproduit ici).

## Résumé

- Le corpus d'entraînement et de validation compte **6 000 messages** : 2 882 publics traduits (48 %) et 3 118 générés (52 %).
- Les étiquettes des tickets publics sont **recalculées** à l'assemblage avec les règles actuelles de `config/public_label_mapping.yaml` : les fichiers traduits portaient d'anciennes étiquettes (avant la correction de la PR #47), et rien n'est retraduit.
- Répartition 85 / 15 entre entraînement (5 103) et validation (897), **stratifiée par catégorie**.
- Deux jeux de test : **test externe** (457 tickets réels tasksource, jamais utilisés pour l'entraînement) et **test généré** (180 tickets pour `backup`, `procurement`, `admin_billing`, qui n'ont aucun vrai ticket de test). Le test généré est **optimiste** (voir les limites).
- **Aucune fuite** : le script vérifie qu'aucun texte identique ou quasi identique ne se trouve dans deux jeux différents, et s'arrête avec une erreur sinon.
- Les tickets **douteux** (étiquette de catégorie moins sûre) restent marqués, pour calculer les scores avec et sans eux.

## Méthode

### 1. Étiquettes recalculées

Pour chaque ticket public, `load_mapping()` (`src/data/label_mapping.py`) calcule la catégorie, le type, la priorité et l'indicateur `doubtful` à partir du texte d'origine et des étiquettes d'origine. Un ticket exclu par une règle, ou sans catégorie, serait écarté et compté dans le rapport : aucun ne l'a été.

Les étiquettes **manquantes restent à `null`**. Rien n'est inventé : c'est le cas du type et de la priorité du test externe (voir le tableau de complétude).

### 2. Répartition par catégorie

Pour chaque catégorie :

- **cible** = 6 000 × poids de la catégorie ÷ somme des poids (`free_text.categories` de `config/generator.yaml`, somme 102), arrondie par la méthode du plus grand reste pour que le total fasse exactement 6 000 ;
- **public** = minimum entre les tickets publics disponibles et la cible (tirage reproductible, graine 42) ;
- **généré** = cible moins public.

**Pourquoi.** Les catégories abondantes dans le public (`software`, `network`, `infrastructure`, `security`) sont limitées à leur cible, ce qui évite qu'un classifieur apprenne surtout `software`. Les catégories rares (`messaging`, `printing`, `backup`, `telephony`) gardent **tous** leurs tickets publics, et le générateur comble le reste. Décision du développeur du 31 octobre 2026. Alternative écartée : un tirage au hasard de 3 600 tickets publics, qui laissait `software` à 1 358 messages et portait le corpus à 7 278 messages.

Les chiffres de la page de récupération (2 883 publics et 3 118 générés) dataient d'avant la correction de la PR #47 et d'un arrondi par excès de deux cibles (`infrastructure` et `security`, 471 chacune, soit 6 001 au total). Le calcul du script donne 470 pour `security` : 2 882 publics, 3 118 générés, 6 000 exactement.

### 3. Entraînement et validation

Le split 85 / 15 est **stratifié par catégorie** : chaque catégorie donne environ 15 % de ses messages à la validation. Les **quasi-doublons restent du même côté** : deux tickets dont les 50 premiers caractères normalisés sont identiques forment un groupe, et le groupe entier va dans l'entraînement ou dans la validation. Une clé qui apparaîtrait dans deux catégories est envoyée entièrement dans l'entraînement.

La clé de quasi-doublon est le texte en minuscules, sans balises de pseudonymisation, réduit aux lettres et coupé à 50 caractères (`template_key`). Pour les tickets **générés**, la clé porte sur **tout le texte** : leurs objets viennent d'une courte liste de modèles, une clé de 50 caractères mettrait des familles entières du même côté par construction.

### 4. Test externe

Les 457 tickets de tasksource ne servent **jamais** à l'entraînement. Tout ticket public d'entraînement dont la clé de quasi-doublon coïncide avec un ticket du test externe est retiré du côté entraînement (aucun cas dans les données réelles).

### 5. Test généré

Les catégories `backup`, `procurement` et `admin_billing` n'ont **aucun vrai ticket de test** (tasksource n'en fournit pas). Un test généré de 60 tickets par catégorie les couvre. Il est produit avec **une autre graine** (4 242) : autres clients fictifs, autres tirages. Le script écarte tout texte déjà présent dans l'entraînement, la validation ou le test externe, puis garde les 60 premiers de chaque catégorie.

### 6. Format et confidentialité

Chaque ligne contient : `id`, `source` (`public` ou `generated`), `text` (sujet et corps en français, joints par un retour à la ligne), `category`, `type`, `priority`, `doubtful`. Le texte n'est **jamais modifié** : les balises de pseudonymisation du jeu public (`[NAME]`, `[SERVER]`…) et les faux secrets du générateur (`FAKE-…`) sont conservés tels quels. Le script n'écrit aucun contenu de ticket dans ses messages ni dans le rapport. Les fichiers de sortie sont dans `data/processed/corpus/` (ignoré par Git).

## Volumes réels

Mesures du 31 octobre 2026. « Disponible » compte les tickets publics après étiquetage (7 682). « Test externe » et « test généré » sont des jeux à part, hors des 6 000.

### Par catégorie : cible, public, généré

| Catégorie | Cible | Public disponible | Public gardé | Généré |
|---|---|---|---|---|
| `network` | 588 | 1 979 | 588 | 0 |
| `messaging` | 706 | 33 | 33 | 673 |
| `workstation` | 706 | 568 | 568 | 138 |
| `software` | 588 | 2 977 | 588 | 0 |
| `accounts` | 706 | 137 | 137 | 569 |
| `printing` | 412 | 12 | 12 | 400 |
| `infrastructure` | 471 | 1 347 | 471 | 0 |
| `backup` | 353 | 8 | 8 | 345 |
| `security` | 470 | 614 | 470 | 0 |
| `telephony` | 412 | 7 | 7 | 405 |
| `procurement` | 294 | 0 | 0 | 294 |
| `admin_billing` | 294 | 0 | 0 | 294 |
| **Total** | **6 000** | **7 682** | **2 882** | **3 118** |

### Par catégorie et par jeu

Les colonnes « Entraînement » et « Validation » donnent le total, dont les tickets publics et générés entre parenthèses.

| Catégorie | Entraînement | Validation | Test externe | Test généré |
|---|---|---|---|---|
| `network` | 502 (502 + 0) | 86 (86 + 0) | 13 | 0 |
| `messaging` | 600 (28 + 572) | 106 (5 + 101) | 73 | 0 |
| `workstation` | 600 (479 + 121) | 106 (89 + 17) | 5 | 0 |
| `software` | 500 (500 + 0) | 88 (88 + 0) | 53 | 0 |
| `accounts` | 600 (117 + 483) | 106 (20 + 86) | 233 | 0 |
| `printing` | 350 (11 + 339) | 62 (1 + 61) | 32 | 0 |
| `infrastructure` | 401 (401 + 0) | 70 (70 + 0) | 13 | 0 |
| `backup` | 300 (7 + 293) | 53 (1 + 52) | 0 | 60 |
| `security` | 400 (400 + 0) | 70 (70 + 0) | 9 | 0 |
| `telephony` | 350 (6 + 344) | 62 (1 + 61) | 26 | 0 |
| `procurement` | 250 (0 + 250) | 44 (0 + 44) | 0 | 60 |
| `admin_billing` | 250 (0 + 250) | 44 (0 + 44) | 0 | 60 |
| **Total** | **5 103** (2 451 + 2 652) | **897** (431 + 466) | **457** | **180** |

### Complétude des étiquettes

Nombre de lignes avec une valeur, par champ. Un total inférieur au nombre de lignes signifie que l'étiquette manque (valeur `null`).

| Jeu | Lignes | Catégorie | Type | Priorité | Douteuses |
|---|---|---|---|---|---|
| Entraînement | 5 103 | 5 103 | 5 103 | 5 103 | 325 |
| Validation | 897 | 897 | 897 | 897 | 52 |
| Test externe | 457 | 457 | 192 | 2 | 29 |
| Test généré | 180 | 180 | 180 | 180 | 0 |

Test externe, selon l'indicateur `doubtful` :

| Sous-ensemble | Lignes | Type renseigné | Priorité renseignée |
|---|---|---|---|
| Non douteux | 428 | 177 | 2 |
| Douteux | 29 | 15 | 0 |

Pour évaluer le modèle, calculer les scores **sur les tickets douteux et non douteux séparément** : les douteux sont surreprésentés dans la sélection des 50 tickets relus (12 sur 50, soit 24 %, contre 6 % dans le test externe).

### Absence de fuite

| Paires de jeux contrôlées | Textes identiques | Clés de quasi-doublon communes |
|---|---|---|
| Entraînement et validation | 0 | 0 |
| Entraînement et test externe | 0 | 0 |
| Entraînement et test généré | 0 | 0 |
| Validation et test externe | 0 | 0 |
| Validation et test généré | 0 | 0 |
| Test externe et test généré | 0 | 0 |

## Limites

- **`workstation` peu représenté au test externe** : 5 tickets seulement (après correction de la PR #47, les imprimantes ont rejoint `printing`). Le score de cette catégorie sera très instable ; il est à lire avec prudence, ou à compléter par la validation.
- **`accounts` majoritaire au test externe, avec des quasi-doublons** : 233 tickets sur 457 (51 %), mais seulement 95 clés de quasi-doublon distinctes. Le score global du test externe est donc surtout un score sur `accounts`. Au total, le test externe compte 312 clés distinctes pour 457 tickets. Lire les scores **par catégorie**, et le macro-F1 plutôt que l'exactitude globale.
- **Test généré optimiste** : ses textes viennent des **mêmes modèles de phrases** que ceux de l'entraînement (même fichier `src/data/templates.py`). Aucun texte n'est identique, mais les formulations de fond se retrouvent. Un bon score sur ce test prouve que le modèle sait reconnaître les formulations vues, pas qu'il généralise à de vrais tickets. Il ne remplace pas un test réel : pour ces trois catégories, la validation reste à compléter plus tard par de vrais tickets relus ou par des cas ajoutés par le développeur.
- **Type et priorité presque absents de tasksource** : 192 types sur 457, 2 priorités sur 457. Les tickets publics d'entraînement ont un type et une priorité, mais **uniquement** `incident` et `demande de service`, et les priorités P2 à P4 (aucun P1, aucun type `information`). Ces cas viennent uniquement du générateur. Les 50 tickets relus par le développeur sont les seuls vrais tickets avec un type et une priorité vérifiés (voir plus bas).
- **Part générée majoritaire** (52 %), conséquence de la décision de limiter le public à la cible : les catégories rares sont majoritairement artificielles (de 81 % de générés pour `accounts` à 100 % pour `procurement` et `admin_billing`, avec 95 % pour `messaging`, 97 % pour `printing` et 98 % pour `backup` et `telephony`).
- **Variété du générateur limitée** : voir la mesure ci-dessous.

### Variété des textes générés

Mesure sur les 3 118 textes générés d'entraînement et de validation, après l'enrichissement des modèles de phrases :

| Mesure | Valeur |
|---|---|
| Textes distincts (texte exact) | 3 111 sur 3 118 (99,8 %) |
| Textes distincts après retrait des données fictives (noms, adresses, numéros, machines) | 3 060 sur 3 118 (98,1 %) |
| Objets de message distincts (modèles de phrases réellement utilisés) | 140 |

Les deux premiers chiffres sont élevés parce que les formules de politesse, l'urgence, les durées et les noms varient d'un message à l'autre. Le troisième est plus parlant : **140 objets pour 3 118 messages**, soit environ 22 messages par modèle d'objet. Avant l'enrichissement des modèles de phrases (quatre de plus par catégorie pour huit catégories très demandées), il y en avait 110, soit environ 28 messages par objet. La variété de fond reste donc limitée : c'est la raison de l'évaluation sur des tickets **réels**.

## Premier contrôle avec un modèle simple

Lors de la relecture de la PR, un modèle simple (TF-IDF et régression logistique, script jetable non versionné) a été entraîné pour vérifier que le corpus se comporte correctement. **Ce n'est pas l'évaluation du modèle du projet**, qui reste à faire en E3. Le macro-F1 est la moyenne des scores F1 des catégories, chaque catégorie pesant autant.

| Jeu d'entraînement | Macro-F1 sur le test externe | Exactitude sur le test externe |
|---|---|---|
| Corpus retenu | 0,30 | 0,34 |
| Corpus retenu, balises retirées | 0,31 | 0,36 |
| Public seul (7 682 tickets) | 0,21 | 0,21 |
| Public limité à 70 % de la cible | 0,30 | 0,32 |
| Public limité à 50 % de la cible | 0,33 | 0,33 |
| Généré seul (6 000 tickets) | 0,40 | 0,44 |

Sur le jeu de validation, le corpus retenu obtient pourtant un macro-F1 de 0,89, avec une exactitude de 73 % sur les tickets publics et de 100 % sur les tickets générés.

Ce que ces mesures montrent :

- **Le score de validation est trompeur.** Le modèle reconnaît les modèles de phrases du générateur : les 100 % ne prouvent rien. La validation sert à comparer des réglages, pas à annoncer un résultat.
- **Le modèle reconnaît l'origine d'un texte.** Il distingue public et généré avec 100 % d'exactitude sur la validation. Or quatre catégories (`network`, `software`, `infrastructure`, `security`) ne contiennent que du public, et d'autres presque que du généré.
- **Corriger seulement ce mélange ne suffit pas.** Limiter la part publique change peu le score : l'écart principal semble venir ailleurs.
- **Les vrais tickets du test ne ressemblent pas à l'entraînement.** Longueur médiane de 80 caractères au test externe, contre 501 pour les tickets publics d'entraînement et 286 pour les générés.
- **Les balises ne sont pas homogènes.** 63 % des tickets du test externe contiennent une balise entre crochets, 4 % des tickets publics d'entraînement une balise entre chevrons, et 25 % des générés une adresse fictive en clair. Les retirer ne change presque rien au score, mais une convention unique reste à appliquer avant l'entraînement.

Deux réserves. Les étiquettes du test externe ne sont pas encore relues : une partie de l'écart peut venir d'elles, et la relecture des 50 tickets aidera à trancher. Par ailleurs, ces comparaisons ont utilisé le test externe : **aucun choix de corpus n'en a été déduit**, sinon ce test ne serait plus indépendant. La suite est suivie dans une Issue dédiée.

## Relecture des 50 tickets

Le script `scripts/prepare_reference_review.py` sélectionne 50 tickets du test externe (quotas par catégorie, rotation sur les règles d'étiquetage, quasi-doublons écartés, graine 42, un ticket forcé dont la balise n'a pas été restaurée) et prépare un fichier Excel. Le développeur y confirme la catégorie et renseigne **le type et la priorité**. Le script **refuse d'écraser** un fichier existant (sauf option `--force`), car le développeur y saisit sa relecture à la main.

Vérification : exécuté vers un fichier temporaire, le script reproduit **les 50 mêmes identifiants, dans le même ordre**, que le fichier préparé le 31 octobre 2026.

## Reproduire

Prérequis : les trois fichiers traduits sont dans `data/raw/public/` (voir [Récupération et traduction](recuperation-traduction.md)). Aucune donnée n'est dans le dépôt.

```bash
# Corpus : 4 fichiers JSONL et report.json dans data/processed/corpus/
uv run python scripts/assemble_corpus.py

# Autres dossiers
uv run python scripts/assemble_corpus.py --public-dir data/raw/public --out-dir data/processed/corpus

# Fichier de relecture (groupe data : openpyxl)
uv run --group data python scripts/prepare_reference_review.py --output relecture.xlsx
```

L'assemblage prend quelques secondes et deux exécutions donnent des fichiers **identiques octet pour octet** (graine 42 pour l'entraînement, 4 242 pour le test généré).

Tests (sans donnée réelle, sans réseau) :

```bash
uv run --group dev pytest tests/test_corpus.py tests/test_generator_categories.py tests/test_prepare_reference_review.py
```

## Ce qui n'a pas été vérifié

- La qualité des étiquettes des tickets publics : les règles de correspondance restent une **proposition** à valider. Les 50 tickets relus par le développeur donneront un taux d'accord (l'Issue #46 reste ouverte jusqu'à cette relecture).
- Le modèle du projet n'est pas encore entraîné : seul le contrôle simple décrit plus haut donne une première indication, sans réglage ni validation croisée.
- Le choix de 60 tickets par catégorie pour le test généré est un compromis (assez pour un score stable, peu pour ne pas peser) non encore discuté.
- Le seuil de quasi-doublon (50 caractères) est une convention : il n'a pas été comparé à d'autres seuils ni à une mesure de similarité.

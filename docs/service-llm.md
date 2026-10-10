# Service LLM (Groq et Ollama)

Cette page documente la preuve de concept du service LLM (compétence C8, bloc E2) : accès, installation, configuration, fonctionnement, données échangées et mesure.

## Rôle du service

Pour chaque ticket, l'application **suggère une piste de résolution** au technicien grâce à un modèle de langage (LLM) existant. Le technicien décide : l'outil n'agit jamais seul.

- **Groq** (offre gratuite) est le fournisseur principal.
- **Ollama**, installé en local, est le fournisseur de secours. Ce repli est **désactivable** : l'usage des ressources de la machine locale reste un choix.

Cette brique est distincte du classifieur entraîné dans le projet (bloc E3), qui n'est jamais remplacé par un service externe.

Le code se trouve dans `src/llm/` :

| Fichier | Contenu |
|---|---|
| `config.py` | Lecture et validation de la configuration (variables d'environnement) |
| `client.py` | Client unique, `complete(prompt)`, nouvelles tentatives et bascule |

Un **seul client** suffit : Groq et Ollama exposent tous deux une API compatible OpenAI, donc le SDK Python `openai` sert pour les deux. Seules l'adresse, le modèle et la clé changent.

## Installation et accès

### Dépendances

Elles sont déclarées dans `pyproject.toml` et figées dans `uv.lock` : `openai` (client) et `python-dotenv` (lecture du fichier `.env`).

```bash
uv sync --locked
```

### Créer une clé Groq

1. Créer un compte gratuit sur la console Groq (<https://console.groq.com>).
2. Ouvrir la rubrique des clés d'API et créer une clé.
3. Copier `.env.example` en `.env`, puis renseigner `GROQ_API_KEY`.

Le fichier `.env` est ignoré par Git : la clé ne doit **jamais** être écrite dans le code ni committée.

### Installer Ollama (secours, facultatif)

1. Installer Ollama depuis <https://ollama.com>.
2. Télécharger le modèle par défaut, assez petit pour fonctionner sur CPU : `ollama pull gemma3:4b` (modèle sans raisonnement, retenu après mesure ; voir « Résultats de mesure »).
3. Activer le repli en mettant `LLM_FALLBACK_PROVIDER=ollama` dans `.env`.

## Variables d'environnement

| Variable | Rôle | Valeur par défaut (`.env.example`) |
|---|---|---|
| `LLM_PROVIDER` | Fournisseur principal : `groq` ou `ollama` | `groq` |
| `LLM_FALLBACK_PROVIDER` | Repli : `ollama`, ou **vide = pas de repli** | vide |
| `GROQ_API_KEY` | Clé d'API Groq (obligatoire si Groq est utilisé) | vide |
| `GROQ_BASE_URL` | Adresse de l'API Groq | `https://api.groq.com/openai/v1` |
| `GROQ_MODEL` | Modèle Groq | `openai/gpt-oss-20b` |
| `OLLAMA_BASE_URL` | Adresse d'Ollama | `http://localhost:11434/v1` |
| `OLLAMA_MODEL` | Modèle Ollama | `gemma3:4b` |
| `LLM_MAX_RETRIES` | Nouvelles tentatives après le premier essai | `5` |
| `LLM_BACKOFF_BASE_SECONDS` | Attente avant la 1re nouvelle tentative | `2` |
| `LLM_BACKOFF_MAX_SECONDS` | Plafond de l'attente | `30` |

La configuration est validée au démarrage : une variable obligatoire manquante, un fournisseur inconnu, un repli identique au principal ou un nombre invalide produisent une erreur explicite (`ConfigError`). Seuls les fournisseurs réellement utilisés sont contrôlés.

### Choix du modèle Groq

`openai/gpt-oss-20b` figure parmi les modèles de **production** de la page « Supported Models » de la documentation Groq (<https://console.groq.com/docs/models>), au moment de la rédaction (octobre 2026). C'est le plus rapide et le moins cher de cette catégorie. Les modèles Llama 3.1 8B et 3.3 70B y sont indiqués comme modèles « enterprise » (accès sur contact commercial) ; ils ne sont donc pas retenus par défaut. Le modèle est un simple paramètre : il pourra changer après le benchmark du bloc E2.

## Nouvelles tentatives et bascule

```text
appel au principal
  ├─ succès → résultat
  └─ erreur 429, réseau ou 5xx → attente (backoff) → nouvelle tentative
        └─ tentatives épuisées (ou erreur non transitoire, ex. clé invalide)
              ├─ repli configuré → même logique avec Ollama
              └─ pas de repli → exception LLMError
```

- **Erreurs transitoires** (429, coupure réseau, délai dépassé, erreur serveur 5xx) : nouvelle tentative.
- **Attente** : `base × 2^(n-1)` secondes (2, 4, 8, 16, 30…), plafonnée par `LLM_BACKOFF_MAX_SECONDS`. Si la réponse contient l'en-tête `retry-after`, l'attente est au moins égale à cette valeur (toujours plafonnée).
- **Erreurs non transitoires** (clé invalide, requête refusée) : pas de nouvelle tentative, passage direct au repli, car réessayer ne changerait rien.
- Les nouvelles tentatives automatiques du SDK `openai` sont désactivées (`max_retries=0`) pour que tout passe par notre logique, journalisée et bornée.

Résultat de `complete(prompt)` : un objet `LLMResult` contenant le texte, le fournisseur, le modèle, la latence en millisecondes et les nombres de tokens en entrée et en sortie.

## Données envoyées et journalisation (RGPD)

**Données envoyées au fournisseur** : le texte du prompt. À terme, ce texte sera **pseudonymisé avant tout envoi** à Groq (règle du projet). Pour cette POC, le script de mesure n'utilise que des **textes fictifs** inventés : aucune donnée réelle.

**Journalisation** (module `logging`) : uniquement des métadonnées.

| Journalisé | Jamais journalisé |
|---|---|
| fournisseur, modèle | contenu du prompt |
| latence, tokens d'entrée et de sortie | contenu de la réponse |
| numéro de tentative | message d'erreur du fournisseur (peut citer le contenu) |
| code d'erreur (statut HTTP ou type d'exception) | clé d'API |

Ces journaux fournissent aussi les premières métriques de monitoring (latence, erreurs, tokens) ; leur export vers Prometheus viendra dans un second temps.

## Tester

Les tests n'effectuent **aucun appel réseau** : le SDK est remplacé par un faux client, et les attentes du backoff sont neutralisées.

```bash
uv run pytest tests/test_llm_config.py tests/test_llm_client.py
```

Ils couvrent la configuration, le succès simple, la nouvelle tentative sur 429, l'en-tête `retry-after`, l'épuisement puis la bascule, le repli désactivé, et l'absence de contenu du prompt dans les journaux.

## Mesurer la latence

Le script envoie N appels sur des textes de tickets fictifs et affiche la latence moyenne et le 95e percentile (p95) par fournisseur. Il appelle les vrais services : le lancer volontairement, après avoir renseigné `.env`.

```bash
uv run python scripts/llm_poc.py 20                     # fournisseur de LLM_PROVIDER
uv run python scripts/llm_poc.py 20 --provider ollama   # un fournisseur précis, sans repli
```

## Résultats de mesure

Première mesure réelle le 10 octobre 2026, sur le poste de développement (Windows 11, 12 cœurs, 15 Go de RAM, sans GPU), avec les textes fictifs de `scripts/llm_poc.py`. Le processeur et la mémoire ont été relevés toutes les 2 secondes pendant la mesure.

### Latence

| Fournisseur / modèle | Appels | Latence moyenne | p95 | Échecs | Tokens de sortie |
|---|---|---|---|---|---|
| Groq / `openai/gpt-oss-20b` | 6 | 739 ms | 1 522 ms (premier appel) | 0 | 160 à 500 |
| Ollama / `qwen3:4b` (CPU) | 1 (contrôlé) | délai de 60 s dépassé | — | 1 sur 1 | — |
| Ollama / `gemma3:4b` (CPU) | 2 | 28 s au premier appel (chargement du modèle compris), 13 s ensuite | — | 0 | 115 à 175 |

Aucune erreur 429 n'a été observée : six appels restent très en dessous des quotas du free tier.

### Charge sur le poste

| Phase | CPU moyen | CPU max | RAM libre minimale |
|---|---|---|---|
| Repos (référence) | 5 % | 11 % | 3 768 Mo |
| Appels Groq | 14 % | 41 % | 3 695 Mo |
| Ollama `qwen3:4b` | 51 à 53 % | 98 % | 826 Mo |
| Ollama `gemma3:4b` | 38 % | 61 % | 2 219 Mo |

### Conclusions

- **Groq convient comme fournisseur principal** : moins d'une seconde par réponse et une charge négligeable sur le poste, puisque le calcul est fait chez le fournisseur.
- **`gpt-oss-20b` est un modèle à raisonnement** : il produit jusqu'à 500 tokens pour une réponse demandée en trois lignes. C'est sans conséquence sur la latence ici, mais cela consomme davantage le quota de tokens.
- **`qwen3:4b` est écarté comme modèle de secours** : sa phase de raisonnement dépasse le délai de 60 s sur CPU. Cette mesure a révélé un défaut du client, qui réessayait le délai dépassé jusqu'à 6 fois et bloquait l'appel plus de 7 minutes. Le défaut est suivi dans l'Issue #19.
- **`gemma3:4b` devient le modèle de secours par défaut** : 13 s par réponse une fois chargé, une charge acceptable, des réponses en français exploitables. La qualité est inférieure à celle de Groq (une réponse a proposé de vérifier « la pile de l'imprimante »), ce qui est acceptable pour un secours ponctuel.
- **Le repli sur Ollama reste désactivé par défaut** (`LLM_FALLBACK_PROVIDER` vide) : il mobilise environ 3 Go de RAM et la moitié du processeur pendant l'appel.

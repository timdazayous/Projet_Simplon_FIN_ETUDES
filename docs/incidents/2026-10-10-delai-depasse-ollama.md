# Incident : délai dépassé réessayé 6 fois (Ollama)

**Date** : 10 octobre 2026. **Issue** : #19. **Correction** : PR #21. **Compétence visée** : C21 (bloc E5), débogage d'un incident depuis l'outil de suivi, correction par une PR.

## Résumé

Lors de la première mesure réelle du service LLM, un appel vers Ollama n'a pas abouti en plus de 10 minutes. Le client réessayait un **délai dépassé** jusqu'à 6 fois, comme une simple erreur réseau. Il a été corrigé : un délai dépassé n'est plus réessayé, et le délai est désormais réglable par fournisseur.

## Symptôme

Avec `LLM_PROVIDER=ollama` et `OLLAMA_MODEL=qwen3:4b`, la commande `scripts/llm_poc.py 3 --provider ollama` n'a pas terminé ses 3 appels en plus de 10 minutes. Elle a été arrêtée à la main. Pendant le blocage, le poste était fortement sollicité : processeur à 51 % en moyenne (pic à 98 %) et mémoire libre tombée à 826 Mo (3,8 Go au repos).

## Environnement

- Poste de développement Windows 11, 12 cœurs, 15 Go de RAM, sans GPU (Ollama indique « 100% CPU »).
- Ollama 0.30.10, modèle `qwen3:4b` (3,2 Go en mémoire, contexte 4096).
- Client `src/llm/client.py` (PR #18) : délai de requête de 60 s, `LLM_MAX_RETRIES=5`, attente de base de 2 s, plafonnée à 30 s.

## Journaux

Les journaux ne contiennent que des métadonnées (règle RGPD du projet). Reproduction contrôlée avec un seul appel et `LLM_MAX_RETRIES=0` :

```text
23:18:45 (début)
23:19:48 provider=ollama model=qwen3:4b attempt=1/1 error=APITimeoutError
23:19:48 provider=ollama model=qwen3:4b failed error=APITimeoutError next=none
durée totale 62 s
```

## Débogage

1. **Mesure** : relevé du processeur et de la mémoire toutes les 2 secondes pendant l'appel. Il montre que le modèle calcule en continu et qu'il ne s'agit pas d'un blocage réseau. Pour comparaison, `gemma3:4b` répond en 28 s au premier appel (chargement compris) puis 13 s.
2. **Reproduction contrôlée** : un seul appel avec `LLM_MAX_RETRIES=0`. Le délai de 60 s est bien dépassé (62 s au total, erreur `APITimeoutError`). Le modèle est donc trop lent : `qwen3:4b` est un modèle « à raisonnement », qui génère une longue réflexion avant sa réponse, et le CPU seul ne suit pas.
3. **Lecture du code** : dans `client.py`, la liste `RETRYABLE_ERRORS` contient `openai.APIConnectionError`. Or `APITimeoutError` **hérite** de `APIConnectionError` : un délai dépassé était donc traité comme une panne réseau passagère.
4. **Cause identifiée** : avec 5 nouvelles tentatives, un appel coûtait au pire 6 × 60 s d'attente de réponse, plus 2 + 4 + 8 + 16 + 30 s d'attente entre essais, soit environ **7 minutes** par appel et plus de 20 minutes pour 3 appels. Réessayer ne sert à rien : un modèle trop lent restera trop lent.

## Test de reproduction

Avant toute correction, un test a été ajouté (commit « Reproduit le bug #19 par un test »). Un faux client lève `APITimeoutError` à chaque appel ; le test exige une seule tentative et aucune attente de backoff. Il échoue sur le code d'origine :

```text
>       assert groq.calls == 1
E       assert 3 == 1
E        +  where 3 = <test_llm_client.FakeSDK object at ...>.calls
FAILED tests/test_llm_client.py::test_timeout_is_not_retried_and_does_not_back_off
FAILED tests/test_llm_client.py::test_timeout_goes_straight_to_fallback
2 failed, 13 passed
```

Les 3 appels (1 essai + 2 nouvelles tentatives dans le test) confirment le défaut sans aucun appel réel à Ollama ni à Groq.

## Correction

- `APITimeoutError` est interceptée **avant** les erreurs transitoires et n'est plus réessayée : le client passe directement au repli s'il existe, sinon il lève `LLMError`. Les erreurs 429, 5xx et les coupures réseau qui ne sont pas des délais dépassés gardent leur nouvelle tentative avec attente progressive.
- Le délai devient configurable **par fournisseur** : `GROQ_TIMEOUT_SECONDS` (30 s par défaut) et `OLLAMA_TIMEOUT_SECONDS` (120 s par défaut), strictement positifs, stockés dans la configuration du fournisseur et transmis au SDK. Groq répond en moins de 2 s ; un modèle local sur CPU a besoin de plus.
- Le journal du délai dépassé reste en métadonnées seules (fournisseur, modèle, tentative, type d'erreur).

**Alternatives écartées** : réessayer une seule fois (le gain est quasi nul, car un modèle lent reste lent, et l'attente double) ; garder un délai unique de 60 s pour tous (trop court pour un modèle local, trop long pour Groq).

## Validation

Les deux tests de reproduction passent. Les tests de configuration (valeur par défaut, valeur personnalisée, valeur invalide) et celui de la fabrique du client (le bon délai est transmis au SDK) sont verts. La couverture de `src/llm` reste à 100 %. Les contrôles `ruff` et la construction de la documentation passent.

## Prévention

- Le test de non-régression garde en permanence le comportement attendu (une tentative, aucune attente).
- Les délais par fournisseur évitent qu'un réglage adapté à Groq pénalise Ollama, et inversement.
- Le modèle de secours par défaut est `gemma3:4b` (sans raisonnement, 13 s par réponse), à la place de `qwen3:4b`. Voir [Service LLM](../service-llm.md).

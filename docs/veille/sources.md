# Sources de veille

Chaque source est évaluée selon une grille de fiabilité avant d'être retenue. Les flux RSS indiqués ont été vérifiés le 7 octobre 2026 : ils sont valides et ont publié dans les semaines précédentes.

## Grille de fiabilité

Une source est retenue si elle satisfait l'essentiel des critères suivants :

1. **Auteur identifié** : on sait qui publie.
2. **Compétence** : l'auteur ou l'organisme est reconnu sur le sujet.
3. **Indépendance** : l'absence d'intérêt personnel ou commercial est vérifiée, ou l'intérêt est connu et pris en compte.
4. **Qualité du contenu** : publication récente et datée, sources citées, langue correcte.
5. **Structure** : site organisé, articles faciles à retrouver.
6. **Accessibilité** : les sites qui respectent les normes d'accessibilité sont privilégiés.
7. **Recoupement** : l'information peut être confirmée par une autre source de confiance.

Une source dont l'indépendance est limitée (éditeur d'un outil, association engagée) peut être retenue comme **source primaire sur son propre sujet**, à condition de recouper ses analyses ailleurs.

## Sources retenues

### Réglementation de l'IA et des données

| Source | Éditeur | Flux | Évaluation |
|---|---|---|---|
| [CNIL — actualités](https://www.cnil.fr/fr) | Autorité administrative indépendante chargée de la protection des données | `https://www.cnil.fr/fr/rss.xml` | Source officielle et primaire sur le RGPD ; publications datées ; organisme public soumis aux obligations d'accessibilité numérique. **Fiabilité élevée.** |
| [AI Act Explorer](https://artificialintelligenceact.eu/) | Future of Life Institute, association | `https://artificialintelligenceact.eu/feed/` | Suivi détaillé du texte et de son calendrier ; association qui défend des positions sur la sûreté de l'IA, donc **analyses à recouper** avec le texte officiel publié au Journal officiel de l'Union européenne (EUR-Lex). **Fiabilité bonne pour le suivi, à recouper pour l'interprétation.** |

### Services d'inférence LLM et modèles

| Source | Éditeur | Flux | Évaluation |
|---|---|---|---|
| [Ollama — blog](https://ollama.com/blog) | Éditeur d'Ollama | `https://ollama.com/blog/rss.xml` | Source primaire sur l'outil utilisé ; éditeur, donc discours promotionnel possible. **Fiable pour les annonces de l'outil.** |
| [Ollama — versions](https://github.com/ollama/ollama/releases) | Éditeur d'Ollama | `https://github.com/ollama/ollama/releases.atom` | Notes de version officielles : changements exacts et datés. **Fiabilité élevée.** |
| [Groq — journal des modifications](https://console.groq.com/docs/changelog) et [dépréciations](https://console.groq.com/docs/deprecations) | Groq | Pas de flux : consultation directe en séance | Source primaire sur les modèles disponibles et les retraits annoncés, qui peuvent casser l'intégration du projet. **Fiabilité élevée sur ces faits.** |
| [Hugging Face — blog](https://huggingface.co/blog) | Hugging Face, entreprise | `https://huggingface.co/blog/feed.xml` | Articles techniques signés, souvent avec code et références ; intérêt commercial pour sa plateforme. **Fiabilité bonne, à recouper.** |
| [Simon Willison — blog](https://simonwillison.net/) | Simon Willison, développeur indépendant (co-créateur du framework Django) | `https://simonwillison.net/atom/everything/` | Auteur identifié et reconnu, sans produit à vendre sur les sujets traités ; tests concrets et sources systématiquement liées. **Fiabilité élevée.** |

### Outils du projet, sécurité et accessibilité

| Source | Éditeur | Flux | Évaluation |
|---|---|---|---|
| [CERT-FR — avis et alertes](https://www.cert.ssi.gouv.fr/) | ANSSI (agence nationale de la sécurité des systèmes d'information) | `https://www.cert.ssi.gouv.fr/feed/` | Source officielle sur les vulnérabilités ; sert à vérifier les composants du projet (Python, PostgreSQL, GLPI…). **Fiabilité élevée.** |
| [Access42 — blog](https://access42.net/) | Coopérative spécialisée en accessibilité numérique (audit, formation RGAA) | `https://access42.net/feed/` | Experts reconnus du RGAA en France ; articles datés et précis. **Fiabilité élevée.** |
| [Astral — blog](https://astral.sh/blog) | Éditeur d'uv et de ruff | `https://astral.sh/blog/rss.xml` | Source primaire sur deux outils du projet. **Fiable pour les annonces de ses outils.** |
| [Material for MkDocs — versions](https://github.com/squidfunk/mkdocs-material/releases) et [Zensical — versions](https://github.com/zensical/zensical/releases) | Équipe de Material for MkDocs | `https://github.com/squidfunk/mkdocs-material/releases.atom`, `https://github.com/zensical/zensical/releases.atom` | Notes de version officielles ; suivi de la fin de support de Material (Issue #13). **Fiabilité élevée.** |
| [GLPI — versions](https://github.com/glpi-project/glpi/releases) | Teclib' | `https://github.com/glpi-project/glpi/releases.atom` | Notes de version officielles, dont les correctifs de sécurité. **Fiabilité élevée.** |

### Consultées sans flux

| Source | Usage |
|---|---|
| [OWASP — actualités](https://owasp.org/news/) | Évolutions des Top 10 (applications web et API) appliqués au projet |
| [Référentiel RGAA](https://accessibilite.numerique.gouv.fr/) | Texte de référence pour l'accessibilité de l'interface et de la documentation |

## Sources écartées

| Type de source | Raison |
|---|---|
| Publications de « créateurs de contenu » sur les réseaux sociaux | Auteurs rarement qualifiés, sources absentes, objectif d'audience plutôt que d'exactitude |
| Articles de plateformes de blogs ouvertes non signés ou non sourcés | Auteur non identifiable, impossible d'évaluer sa compétence |
| Comparatifs commerciaux de services d'IA (« les 10 meilleurs… ») | Liens d'affiliation et intérêts commerciaux non déclarés |

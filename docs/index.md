# Triage IA des tickets et alertes MSP

Projet de fin de formation **Développeur en intelligence artificielle (Simplon)**.

## Problème

Un MSP (prestataire d'infogérance) reçoit des centaines de tickets et d'alertes par jour dans une file unique. Le tri (catégorie, urgence, équipe, recherche de cas similaires) est manuel, lent et source d'erreurs de routage.

## Solution

Pour chaque ticket entrant, l'application :

1. **classe** le ticket (catégorie, urgence, équipe) avec un modèle entraîné dans le projet ;
2. **suggère une piste de résolution** via un LLM, à partir des tickets résolus et de la documentation ;
3. **apprend des corrections** des techniciens (boucle de feedback, ré-entraînement).

L'outil aide le technicien à décider, il n'agit jamais seul.

> Commanditaire fictif : un MSP d'une trentaine de personnes gérant une soixantaine de PME clientes.

## Contraintes

- Zéro budget : outils gratuits ou open source.
- Pas de GPU : entraînement sur CPU, compatible runner GitHub Actions.
- RGPD : données pseudonymisées avant tout traitement et avant tout envoi à un service externe.

## Dans cette documentation

- [Documentation](documentation.md) : comment ce site est construit et publié.
- [Intégration continue](ci.md) : la chaîne qui vérifie chaque modification.
- [Outil de ticketing](decisions/outil-ticketing.md) : choix entre GLPI et Zammad.

Le code source et le suivi des décisions (fichier `JOURNAL.md`) sont sur le [dépôt GitHub du projet](https://github.com/timdazayous/Projet_Simplon_FIN_ETUDES).

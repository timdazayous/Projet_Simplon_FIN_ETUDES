# Réponses d'exemple de l'API du CERT-FR

Réponses JSON **réduites** de l'API publique du CERT-FR (ANSSI), récupérées le 23 octobre 2026, utilisées par `tests/test_certfr.py` (aucun appel réseau).

- Source : CERT-FR, https://cert.cyber.gouv.fr/avis/json/ et https://cert.cyber.gouv.fr/avis/<référence>/json/
- Licence : Licence Ouverte Etalab 2.0 (réutilisation libre avec mention de la source).
- Description des champs : https://cert.cyber.gouv.fr/openapi.json

| Fichier | Contenu |
|---|---|
| `list_sample.json` | 3 entrées de la liste des avis |
| `avis_1367.json` | Avis complet (Node.js), tel que publié |
| `avis_0251.json` | Avis complet plus ancien (Mozilla Firefox), tel que publié |
| `avis_1366.json` | Avis Splunk, réduit à 3 systèmes affectés, 3 CVE, 2 bulletins et 3 risques |

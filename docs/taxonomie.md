# Taxonomie des tickets

**Statut** : validée par le développeur le 20 octobre 2026 · **Issue** : #6 · **Compétences** : C12 (labellisation des données), C14 (spécifications fonctionnelles)

La taxonomie fixe les étiquettes attribuées à chaque ticket ou alerte : la **catégorie**, le **type**, la **priorité** et l'**équipe**. Elle conditionne le générateur de tickets synthétiques, la labellisation, l'entraînement et les tests sur les données. La façon dont ces étiquettes sont proposées (règles ou modèle) est décrite dans la page [Conception du tri](conception-tri.md).

La version lisible par le code est `config/taxonomy.yaml` : c'est la **référence unique** pour le code et les tests.

## Principes

- **Des classes distinctes** : deux catégories ne doivent pas se recouvrir, sinon le modèle et les humains hésitent et les étiquettes deviennent incohérentes.
- **Un nombre raisonnable de classes** : assez pour un routage utile, pas trop pour que chaque classe ait suffisamment d'exemples.
- **Le sujet et le genre de demande sont séparés** : la catégorie dit *de quoi* parle le ticket, le type dit *quel genre* de demande c'est. Une demande d'information peut porter sur la messagerie comme sur la facturation.
- **Des critères écrits** : définitions, exemples et règles pour les cas ambigus rendent la labellisation reproductible.

## Catégories (le sujet)

| Code | Catégorie | Définition | Exemples |
|---|---|---|---|
| `network` | Réseau et connectivité | Accès à Internet, réseau local, Wi-Fi, VPN, pare-feu, lien opérateur | « Plus d'Internet sur le site de Lyon » ; « Le VPN se déconnecte toutes les 10 minutes » |
| `messaging` | Messagerie et collaboration | Messagerie, calendriers, outils collaboratifs (Microsoft 365, Teams, partages en ligne) | « Je ne reçois plus de mails depuis ce matin » ; « Impossible de partager un fichier dans Teams » |
| `workstation` | Poste de travail | Matériel et système des ordinateurs, périphériques (hors imprimantes) | « Mon PC est très lent au démarrage » ; « Écran noir après la mise à jour » |
| `software` | Logiciels et applications | Installation, mise à jour, licence ou dysfonctionnement d'un logiciel, y compris métier | « Installer Adobe Reader » ; « Le logiciel de comptabilité plante à l'ouverture » |
| `accounts` | Comptes et accès | Création, désactivation, mot de passe, MFA, droits d'accès | « Compte bloqué après trop d'essais » ; « Accès au dossier Compta » |
| `printing` | Impression et numérisation | Imprimantes, copieurs, scanners, files d'impression | « L'imprimante du 2e étage n'imprime plus » ; « Le scan vers mail ne fonctionne pas » |
| `infrastructure` | Serveurs et infrastructure | Serveurs, virtualisation, annuaire, stockage, services centraux | Alerte « disque C: à 95 % sur SRV-FICHIERS » ; « Le serveur de fichiers ne répond plus » |
| `backup` | Sauvegarde et restauration | Échecs ou alertes de sauvegarde, demandes de restauration | Alerte « sauvegarde nocturne en échec » ; « Restaurer un fichier supprimé hier » |
| `security` | Sécurité | Hameçonnage, logiciel malveillant, alerte antivirus ou EDR, suspicion de compromission | « J'ai cliqué sur un lien suspect » ; alerte EDR « comportement de rançongiciel » |
| `telephony` | Téléphonie et mobiles | Téléphonie IP, standard, smartphones et tablettes professionnels | « Le standard ne sonne plus » ; « Configurer ma messagerie sur mon nouveau téléphone » |
| `procurement` | Achats et matériel | Commande, devis ou livraison de matériel et de licences | « Commander un PC pour le nouvel arrivant » ; « Où en est la livraison des écrans ? » |
| `admin_billing` | Administratif et facturation | Factures, contrats, renouvellements, informations administratives du client | « Question sur la dernière facture » ; « Ajouter un site à notre contrat » |

### Règles pour les cas ambigus

| Situation | Règle | Exemple |
|---|---|---|
| Symptôme sur un poste, cause dans un autre domaine | La **cause** si elle est connue, sinon le **symptôme** | « Pas d'Internet sur mon PC » : `network` si tout le site est touché, `workstation` si un seul poste |
| Problème de mot de passe dans un logiciel | `accounts` pour un problème d'identifiant ou de droits, `software` si le logiciel est en panne | « Mot de passe refusé dans l'ERP » : `accounts` |
| Mail suspect | `security` dès qu'il y a suspicion d'hameçonnage | « Mail étrange de la banque » : `security` |
| Alerte de supervision | Selon la **ressource concernée**, pas selon l'outil qui alerte | « Disque plein » : `infrastructure` ; « sauvegarde en échec » : `backup` |
| Matériel en panne ou matériel à acheter | `workstation` (ou la catégorie du matériel) pour une panne, `procurement` pour un achat ou un remplacement à commander | « Mon écran ne s'allume plus » : `workstation` ; « Il me faut un second écran » : `procurement` |
| Licence | `software` pour un problème d'activation ou d'utilisation, `procurement` pour en acheter, `admin_billing` pour une question de facturation | « Commander 5 licences Office » : `procurement` |

## Types (le genre de demande)

| Code | Type | Définition | Exemples |
|---|---|---|---|
| `incident` | Incident | Quelque chose ne fonctionne pas ou fonctionne mal | « L'imprimante n'imprime plus » ; toute alerte de supervision |
| `service_request` | Demande de service | Une action est demandée, rien n'est en panne | « Créer un compte pour un nouvel arrivant » ; « Commander un PC » |
| `information` | Demande d'information | Une question, sans action ni panne | « Comment configurer ma signature de mail ? » ; « Quand expire notre contrat ? » |

Les alertes de supervision sont toujours de type `incident`.

## Priorité

Quatre niveaux, déduits de l'**impact** (combien de personnes ou quelle part de l'activité) et de l'**urgence** (le travail est-il bloqué, existe-t-il un contournement).

| Code | Priorité | Critères | Exemples |
|---|---|---|---|
| `P1` | Critique | Activité arrêtée pour un site ou tout le client, **ou** incident de sécurité en cours | Plus d'Internet sur tout un site ; rançongiciel détecté |
| `P2` | Haute | Service important dégradé pour plusieurs personnes, **ou** une personne bloquée sans contournement | Messagerie très lente pour un service ; dirigeant sans accès à sa messagerie |
| `P3` | Moyenne | Gêne réelle, mais un contournement existe ou une seule personne est touchée | Imprimante en panne alors qu'une autre fonctionne ; poste lent |
| `P4` | Basse | Demande planifiable, question, aucune gêne immédiate | Installer un logiciel la semaine prochaine ; question sur une facture |

Correspondance avec GLPI : `P1` = « Très haute » ou « Majeure », `P2` = « Haute », `P3` = « Moyenne », `P4` = « Basse » ou « Très basse ». Pour les alertes de supervision, la priorité vient de la gravité de l'outil, harmonisée par une table de correspondance (voir [Conception du tri](conception-tri.md)).

## Équipes

| Code | Équipe | Rôle |
|---|---|---|
| `service_desk` | Service desk (N1) | Premier niveau : postes, logiciels, comptes, impression, téléphonie, demandes d'information techniques |
| `systems_network` | Systèmes et réseau (N2/N3) | Serveurs, réseau, sauvegarde, incidents critiques |
| `cloud_collab` | Cloud et collaboration | Microsoft 365, messagerie, outils collaboratifs |
| `security` | Sécurité | Incidents et alertes de sécurité |
| `procurement` | Commandes | Achats, devis et livraisons de matériel et de licences |
| `account_management` | Gestion de compte et administratif | Facturation, contrats, questions administratives |

Les équipes `procurement` et `account_management` reprennent l'organisation réelle d'un MSP, où la gestion des commandes et la gestion de compte sont deux services distincts.

### Règles de routage

L'équipe n'est pas prédite par le modèle : elle est **déduite par des règles**, appliquées dans l'ordre (la première qui s'applique l'emporte). Le technicien peut toujours corriger.

| Ordre | Condition | Équipe |
|---|---|---|
| 1 | Catégorie `security` | `security` |
| 2 | Catégorie `procurement` | `procurement` |
| 3 | Catégorie `admin_billing` | `account_management` |
| 4 | Priorité `P1` et type `incident` | `systems_network` (y compris pour la messagerie : un incident critique est confié au niveau le plus expérimenté, quel que soit le sujet) |
| 5 | Type `information` | `service_desk` |
| 6 | Catégorie `messaging` | `cloud_collab` |
| 7 | Catégorie `network`, `infrastructure` ou `backup` | `systems_network` |
| 8 | Toute autre catégorie | `service_desk` |

## Décisions prises (20 octobre 2026)

| Question du brouillon | Décision |
|---|---|
| Les catégories collent-elles à la réalité ? | Oui. Ajout de `procurement` et `admin_billing`, fréquentes en MSP. |
| Faut-il prédire le type (incident, demande, information) ? | Oui : c'est la bonne place pour les demandes d'information, qui ne sont pas une catégorie. |
| Faut-il tenir compte de l'origine du ticket ? | Oui, comme **information connue à l'arrivée** (canal d'entrée), utilisée par les règles et comme indice par le modèle, jamais prédite. |
| Les équipes sont-elles réalistes ? | Oui, avec deux équipes ajoutées : commandes, et gestion de compte et administratif. |
| Garder la téléphonie ? | Oui : aucune catégorie n'est jugée trop rare. Les données synthétiques respecteront ce choix. |

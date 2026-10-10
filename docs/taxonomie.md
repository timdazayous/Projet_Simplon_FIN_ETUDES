# Taxonomie des tickets

**Statut** : brouillon, à valider par le développeur · **Issue** : #6 · **Compétences** : C12 (labellisation des données), C14 (spécifications fonctionnelles)

La taxonomie fixe les étiquettes que le classifieur apprend à prédire pour chaque ticket : la **catégorie**, la **priorité** et l'**équipe** destinataire. Elle conditionne le générateur de tickets synthétiques, la labellisation, l'entraînement et les tests sur les données.

## Principes de conception

- **Des classes distinctes** : deux catégories ne doivent pas se recouvrir. Sinon, le modèle et les humains hésitent, et les étiquettes deviennent incohérentes.
- **Un nombre raisonnable de classes** : environ 10 catégories. Avec trop de classes, il faut beaucoup plus d'exemples par classe ; avec trop peu, le routage reste trop grossier pour être utile.
- **Des critères écrits** : chaque classe a une définition, des exemples et des règles pour les cas ambigus. C'est ce qui permet une labellisation reproductible.
- **Alignement sur GLPI** : la priorité suit la logique de GLPI (urgence × impact), pour que les étiquettes aient un sens dans l'outil de ticketing.

## Catégories

| Code | Catégorie | Définition | Exemples |
|---|---|---|---|
| `network` | Réseau et connectivité | Accès à Internet, réseau local, Wi-Fi, VPN, pare-feu, lien opérateur | « Plus d'Internet sur le site de Lyon » ; « Le VPN se déconnecte toutes les 10 minutes » ; alerte de supervision « lien WAN down » |
| `messaging` | Messagerie et collaboration | Messagerie, calendriers, outils de travail collaboratif (Microsoft 365, Teams, partages en ligne) | « Je ne reçois plus de mails depuis ce matin » ; « Impossible de partager un fichier dans Teams » |
| `workstation` | Poste de travail | Matériel et système des ordinateurs fixes et portables, périphériques (hors imprimantes) | « Mon PC est très lent au démarrage » ; « Écran noir après la mise à jour Windows » ; « Le clavier ne répond plus » |
| `software` | Logiciels et applications | Installation, mise à jour, licence ou dysfonctionnement d'un logiciel, y compris logiciel métier | « Installer Adobe Reader » ; « Le logiciel de comptabilité plante à l'ouverture » |
| `accounts` | Comptes et accès | Création, désactivation, mot de passe, MFA, droits d'accès à une ressource | « Compte bloqué après trop d'essais » ; « Arrivée d'un nouveau salarié lundi » ; « Accès au dossier Compta » |
| `printing` | Impression et numérisation | Imprimantes, copieurs, scanners, files d'impression | « L'imprimante du 2e étage n'imprime plus » ; « Le scan vers mail ne fonctionne pas » |
| `infrastructure` | Serveurs et infrastructure | Serveurs, virtualisation, annuaire, stockage, services centraux | Alerte « disque C: à 95 % sur SRV-FICHIERS » ; « Le serveur de fichiers ne répond plus » |
| `backup` | Sauvegarde et restauration | Échecs ou alertes de sauvegarde, demandes de restauration | Alerte « sauvegarde nocturne en échec » ; « Restaurer un fichier supprimé hier » |
| `security` | Sécurité | Hameçonnage, logiciel malveillant, alerte antivirus ou EDR, suspicion de compromission | « J'ai cliqué sur un lien suspect » ; alerte EDR « comportement de rançongiciel détecté » |
| `telephony` | Téléphonie et mobiles | Téléphonie IP, standard, smartphones et tablettes professionnels | « Le standard ne sonne plus » ; « Configurer la messagerie sur mon nouveau téléphone » |

### Règles pour les cas ambigus

| Situation | Règle | Exemple |
|---|---|---|
| Symptôme sur un poste, cause dans un autre domaine | On classe selon la **cause** quand elle est connue, sinon selon le **symptôme** | « Pas d'Internet sur mon PC » : `network` si tout le site est touché, `workstation` si un seul poste |
| Problème de mot de passe dans un logiciel | `accounts` si c'est un problème d'identifiant ou de droits, `software` si le logiciel est en panne | « Mot de passe refusé dans l'ERP » : `accounts` |
| Mail suspect | `security` dès qu'il y a suspicion d'hameçonnage, même si l'utilisateur parle de messagerie | « Mail étrange de la banque » : `security` |
| Alerte de supervision | On classe selon la **ressource concernée**, pas selon l'outil qui alerte | Alerte « disque plein » : `infrastructure` ; alerte « sauvegarde en échec » : `backup` |

## Priorité

Quatre niveaux, déduits de l'**impact** (combien de personnes ou quelle part de l'activité) et de l'**urgence** (le travail est-il bloqué, existe-t-il un contournement).

| Code | Priorité | Critères | Exemples |
|---|---|---|---|
| `P1` | Critique | Activité arrêtée pour un site ou tout le client, **ou** incident de sécurité en cours | Plus d'Internet sur tout un site ; rançongiciel détecté |
| `P2` | Haute | Service important dégradé pour plusieurs personnes, **ou** une personne bloquée sans contournement | Messagerie très lente pour un service ; dirigeant sans accès à sa messagerie |
| `P3` | Moyenne | Gêne réelle, mais un contournement existe ou une seule personne est touchée | Imprimante en panne alors qu'une autre fonctionne ; poste lent |
| `P4` | Basse | Demande planifiable, question, aucune gêne immédiate | Installer un logiciel la semaine prochaine ; préparer l'arrivée d'un salarié |

Correspondance avec GLPI : `P1` = priorité « Très haute » ou « Majeure », `P2` = « Haute », `P3` = « Moyenne », `P4` = « Basse » ou « Très basse ».

## Équipes

Organisation proposée pour un MSP d'une trentaine de personnes.

| Code | Équipe | Rôle |
|---|---|---|
| `service_desk` | Service desk (N1) | Premier niveau : demandes simples, comptes, impression, postes, téléphonie |
| `systems_network` | Systèmes et réseau (N2/N3) | Serveurs, réseau, sauvegarde, incidents complexes |
| `cloud_collab` | Cloud et collaboration | Microsoft 365, messagerie, outils collaboratifs |
| `security` | Sécurité | Incidents et alertes de sécurité |

### Équipe par défaut selon la catégorie

| Catégorie | Équipe par défaut |
|---|---|
| `workstation`, `software`, `accounts`, `printing`, `telephony` | `service_desk` |
| `network`, `infrastructure`, `backup` | `systems_network` |
| `messaging` | `cloud_collab` |
| `security` | `security` |

**Exceptions** : un ticket `P1` hors sécurité va directement à `systems_network`, sans passer par le N1. Un problème de compte dans Microsoft 365 (MFA, licence) va à `cloud_collab`.

L'équipe reste une étiquette à part entière que le modèle prédit. La correspondance par défaut sert à générer des données cohérentes et de base de comparaison (baseline par règles).

## Questions ouvertes (à trancher par le développeur)

1. **Les catégories correspondent-elles à la réalité ?** Ton expérience Autotask est la référence : files d'attente, types de tickets, catégories qui se mélangent souvent. Exemples à donner **sans nom de client ni donnée réelle**.
2. **Faut-il aussi prédire le type ITIL** (incident ou demande) ? GLPI le gère nativement. C'est une étiquette facile à apprendre et utile au routage, mais c'est une quatrième sortie à labelliser.
3. **Faut-il distinguer l'origine du ticket** (utilisateur ou supervision) ? C'est souvent connu à l'arrivée (une alerte Zabbix n'est pas rédigée comme un mail d'utilisateur) : ce serait une information d'entrée, pas une étiquette à prédire.
4. **Les quatre équipes** te semblent-elles réalistes pour un MSP de cette taille ?
5. **Téléphonie** : en garder une catégorie à part, ou la fusionner avec `workstation` si elle est rare ?

Une fois ces points tranchés, la taxonomie sera figée dans `config/taxonomy.yaml`, que le code et les tests utiliseront comme référence unique.

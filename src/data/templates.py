"""French text building blocks for the synthetic generator (no LLM, no network).

Placeholders such as ``{host}`` or ``{since}`` are filled by the factories of
``SLOT_FACTORIES``; a placeholder keeps the same value inside one message.
Dictionary keys are taxonomy identifiers; the generator checks at start-up
that they match ``config/taxonomy.yaml`` exactly.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from src.data.fictive import fictive_ip, fictive_secret

# --------------------------------------------------------------------------- slots

SlotFactory = Callable[[random.Random, dict[str, Any]], str]


def _pick(*choices: str) -> SlotFactory:
    return lambda rng, ctx: rng.choice(choices)


def _host(rng: random.Random, ctx: dict[str, Any]) -> str:
    role = rng.choice(("FIC", "AD", "APP", "SQL", "MAIL", "HV", "TS"))
    return f"{ctx['client'].code}-SRV-{role}{rng.randint(1, 4):02d}"


def _colleague(rng: random.Random, ctx: dict[str, Any]) -> str:
    others = [u for u in ctx["client"].users if u is not ctx["user"]]
    return rng.choice(others).first_name


SLOT_FACTORIES: dict[str, SlotFactory] = {
    "user": lambda rng, ctx: ctx["user"].first_name,
    "colleague": _colleague,
    "host": _host,
    "ip": lambda rng, ctx: fictive_ip(rng),
    "port": _pick("443", "3389", "8443", "22", "5432", "8080"),
    "n": lambda rng, ctx: str(rng.choice((2, 3, 4, 5, 8, 12, 15, 20))),
    "qty": lambda rng, ctx: str(rng.choice((2, 3, 4, 5, 6, 10))),
    "since": _pick(
        "depuis ce matin",
        "depuis hier après-midi",
        "depuis lundi",
        "depuis environ une heure",
        "depuis la mise à jour de la nuit",
        "depuis ce midi",
    ),
    "site": _pick(
        "l'agence principale",
        "le deuxième étage",
        "l'entrepôt",
        "le secrétariat",
        "le site annexe",
        "la salle de réunion",
    ),
    "app": _pick(
        "Outlook",
        "Excel",
        "Teams",
        "GestCompta",
        "FactoPro",
        "PayeFacile",
        "StockMaster",
    ),
    "device": _pick("PC portable", "poste fixe", "ordinateur"),
    "os": _pick("Windows 11", "Windows 10", "macOS"),
    "printer": _pick(
        "l'imprimante du couloir",
        "la multifonction du secrétariat",
        "l'imprimante de la comptabilité",
        "le copieur de l'étage",
    ),
    "share": _pick("Commun", "Compta", "Direction", "Projets", "RH"),
    "item": _pick(
        "un écran 27 pouces",
        "un PC portable",
        "une station d'accueil",
        "un casque audio",
        "un onduleur",
        "un switch 24 ports",
        "une imprimante laser",
    ),
    "invoice": lambda rng, ctx: f"FAC-2026-{rng.randint(1000, 9999)}",
    "amount": lambda rng, ctx: f"{rng.randint(80, 4500)},{rng.randint(0, 99):02d} €",
    "month": _pick("septembre", "août", "juillet", "octobre"),
    "phone_model": _pick("un téléphone Android", "un iPhone", "un mobile de service"),
    "contract": lambda rng, ctx: f"CT-{rng.randint(100, 999)}",
    "phone": lambda rng, ctx: ctx["user"].phone,
    "email": lambda rng, ctx: ctx["user"].email,
    "ref": lambda rng, ctx: ctx["ref"],
    "secret": lambda rng, ctx: fictive_secret(rng),
}

# --------------------------------------------------------------------------- tickets

# category -> type -> [(subject, body), ...]
TICKET_TEMPLATES: dict[str, dict[str, list[tuple[str, str]]]] = {
    "network": {
        "incident": [
            (
                "Plus d'accès à Internet {since}",
                "Nous n'avons plus du tout Internet {since} dans {site}. Le voyant WAN du routeur "
                "clignote en orange. Les {n} postes du secteur sont concernés.",
            ),
            (
                "VPN impossible à établir",
                "Je n'arrive plus à me connecter au VPN depuis chez moi : le client reste sur "
                "« connexion en cours » puis affiche un délai dépassé. Cela fonctionnait hier.",
            ),
            (
                "Wifi très lent dans {site}",
                "Le wifi de {site} est extrêmement lent {since}, les pages mettent une minute à "
                "charger et les visios coupent. Le réseau filaire semble normal.",
            ),
        ],
        "service_request": [
            (
                "Ouverture d'un port sur le pare-feu",
                "Pouvez-vous ouvrir le port {port} vers {host} pour notre prestataire ? Son "
                "adresse IP est {ip}. Merci de nous confirmer une fois fait.",
            ),
            (
                "Accès VPN pour un nouvel arrivant",
                "{colleague} rejoint l'équipe lundi. Pourriez-vous lui créer un accès VPN et lui "
                "envoyer la procédure de connexion ?",
            ),
        ],
        "information": [
            (
                "Question sur le débit de notre ligne",
                "Quel est le débit de notre ligne Internet actuelle ? Nous envisageons d'ajouter "
                "des postes et voulons savoir si c'est suffisant.",
            ),
            (
                "Comment donner le wifi à un visiteur ?",
                "Un visiteur vient demain. Comment lui donner accès au wifi invités sans lui "
                "communiquer le mot de passe principal ?",
            ),
        ],
    },
    "messaging": {
        "incident": [
            (
                "Impossible d'envoyer des mails",
                "Mes mails {since} restent bloqués dans la boîte d'envoi avec une erreur "
                "de serveur. Je reçois les mails normalement.",
            ),
            (
                "Teams ne fonctionne plus",
                "Teams se ferme tout seul au démarrage sur mon {device}. J'ai déjà essayé de le "
                "relancer et de redémarrer, sans effet.",
            ),
            (
                "Boîte mail pleine",
                "Outlook m'indique que ma boîte est pleine alors que j'ai tout vidé hier. Je ne "
                "reçois plus rien {since}.",
            ),
        ],
        "service_request": [
            (
                "Création d'une boîte partagée",
                "Nous aimerions une boîte partagée « contact » accessible à {n} personnes. "
                "Pouvez-vous la créer et nous donner les droits ?",
            ),
            (
                "Redirection de mails pendant mon absence",
                "Je suis absent du lundi au vendredi. Pouvez-vous rediriger mes mails vers "
                "{colleague} et activer un message d'absence ?",
            ),
        ],
        "information": [
            (
                "Taille maximale des pièces jointes",
                "Quelle est la taille maximale d'une pièce jointe dans notre messagerie ? Un "
                "client veut nous envoyer un gros fichier.",
            ),
            (
                "Différence entre boîte partagée et liste de diffusion",
                "Pouvez-vous m'expliquer la différence entre une boîte partagée et une liste de "
                "diffusion ? Nous hésitons pour le service commercial.",
            ),
        ],
    },
    "workstation": {
        "incident": [
            (
                "Mon {device} ne démarre plus",
                "Mon {device} reste sur un écran noir au démarrage {since}. Le ventilateur "
                "tourne mais rien ne s'affiche.",
            ),
            (
                "Poste extrêmement lent",
                "Mon {device} est devenu très lent {since} : {app} met plusieurs minutes à "
                "s'ouvrir et la souris saccade.",
            ),
            (
                "Écran qui clignote",
                "L'écran de mon poste clignote et devient noir par moments. J'ai changé le câble "
                "sans résultat.",
            ),
        ],
        "service_request": [
            (
                "Installation de {app} sur un poste",
                "Pouvez-vous installer {app} sur le poste de {colleague} ? Il en a besoin à "
                "partir de la semaine prochaine.",
            ),
            (
                "Préparation d'un poste pour un nouvel arrivant",
                "Un nouveau collaborateur arrive lundi. Merci de préparer un {device} avec "
                "{os}, ses accès et les logiciels habituels.",
            ),
        ],
        "information": [
            (
                "Quand mon poste sera-t-il renouvelé ?",
                "Mon {device} a plus de cinq ans. Est-il prévu dans le plan de renouvellement du "
                "parc, et si oui pour quand ?",
            ),
            (
                "Compatibilité {os}",
                "Nos postes peuvent-ils passer sous {os} ? Je voudrais savoir si {app} sera "
                "toujours compatible.",
            ),
        ],
    },
    "software": {
        "incident": [
            (
                "{app} plante à l'ouverture",
                "{app} affiche une erreur puis se ferme dès que je l'ouvre, {since}. Mes "
                "collègues ont le même souci, nous sommes {n} à ne plus pouvoir travailler "
                "dessus.",
            ),
            (
                "Erreur après la mise à jour de {app}",
                "Depuis la mise à jour, {app} refuse d'enregistrer mes documents et affiche un "
                "message d'erreur incompréhensible. Je peux vous envoyer une capture.",
            ),
            (
                "Licence expirée",
                "{app} indique que la licence a expiré et passe en mode lecture seule {since}.",
            ),
        ],
        "service_request": [
            (
                "Demande de licence {app}",
                "Nous avons besoin de {qty} licences supplémentaires pour {app}. Pouvez-vous "
                "nous faire un devis et les installer ?",
            ),
            (
                "Mise à jour de {app}",
                "Pourriez-vous mettre à jour {app} sur l'ensemble des postes ? Une nouvelle "
                "version est disponible et nous voulons la corriger avant la fin du mois.",
            ),
        ],
        "information": [
            (
                "Existe-t-il une alternative à {app} ?",
                "Nous trouvons {app} peu pratique. Auriez-vous une alternative à nous conseiller, "
                "à budget raisonnable ?",
            ),
            (
                "Où trouver le manuel de {app} ?",
                "Je cherche la documentation de {app} pour former un nouvel arrivant. Y a-t-il "
                "un guide d'utilisation ?",
            ),
        ],
    },
    "accounts": {
        "incident": [
            (
                "Compte verrouillé",
                "Mon compte est verrouillé {since} après plusieurs essais de mot de passe. Je ne "
                "peux plus ouvrir ma session.",
            ),
            (
                "Authentification multifacteur qui ne fonctionne plus",
                "Je ne reçois plus le code de vérification sur mon téléphone, donc impossible de "
                "me connecter à ma messagerie. J'ai changé de téléphone la semaine dernière.",
            ),
            (
                "Accès refusé au dossier {share}",
                "J'obtiens « accès refusé » sur le dossier {share} alors que je "
                "l'utilisais tous les jours.",
            ),
        ],
        "service_request": [
            (
                "Création de compte pour {colleague}",
                "Un nouveau collaborateur arrive lundi. Merci de créer son compte, sa messagerie "
                "et de lui donner accès au dossier {share}.",
            ),
            (
                "Réinitialisation de mot de passe",
                "Pouvez-vous réinitialiser le mot de passe de {colleague} ? Il est en "
                "déplacement et ne peut pas le faire lui-même.",
            ),
            (
                "Suppression du compte d'un ancien salarié",
                "{colleague} a quitté l'entreprise hier. Merci de désactiver son compte et de "
                "transférer ses mails à son responsable.",
            ),
        ],
        "information": [
            (
                "Durée de validité des mots de passe",
                "Tous les combien de temps devons-nous changer nos mots de passe ? Une collègue "
                "pense qu'il n'y a plus d'obligation.",
            ),
            (
                "Comment activer la double authentification ?",
                "Pouvez-vous m'indiquer la marche à suivre pour activer la double "
                "authentification sur mon compte ?",
            ),
        ],
    },
    "printing": {
        "incident": [
            (
                "{printer} n'imprime plus",
                "{printer} n'imprime plus {since}. Les travaux restent dans la file d'attente "
                "et l'écran affiche « erreur 79 ».",
            ),
            (
                "Impression avec des traînées",
                "Les documents sortent avec des traînées grises sur {printer}. Nous avons déjà "
                "remplacé le toner, sans effet.",
            ),
            (
                "Plus de numérisation vers le dossier réseau",
                "Le scan vers le dossier {share} ne fonctionne plus {since} : la machine affiche "
                "un échec d'envoi.",
            ),
        ],
        "service_request": [
            (
                "Installation de {printer} sur mon poste",
                "Pouvez-vous ajouter {printer} sur mon {device} ? Je ne la vois pas dans la "
                "liste des imprimantes.",
            ),
            (
                "Commande de toner",
                "Il nous reste peu de toner pour {printer}. Pouvez-vous en commander {qty} et "
                "nous les livrer ?",
            ),
        ],
        "information": [
            (
                "Imprimer en recto verso par défaut",
                "Est-il possible de configurer l'impression recto verso par défaut pour tout le "
                "service ? Nous voulons économiser du papier.",
            ),
            (
                "Combien coûte une page imprimée ?",
                "Avez-vous une idée du coût par page sur {printer} ? Nous faisons un point sur "
                "nos dépenses.",
            ),
        ],
    },
    "infrastructure": {
        "incident": [
            (
                "Le serveur de fichiers ne répond plus",
                "Le dossier {share} n'est plus accessible {since}. Le serveur {host} semble ne "
                "plus répondre, {n} personnes sont bloquées.",
            ),
            (
                "Application métier inaccessible",
                "{app} ne répond plus, la page reste blanche. Cela touche tout le monde dans "
                "l'entreprise {since}.",
            ),
            (
                "Lenteurs sur le serveur {host}",
                "Tout est très lent sur {host} {since}. Les connexions bureau à distance "
                "mettent plusieurs minutes.",
            ),
        ],
        "service_request": [
            (
                "Ajout d'espace disque sur {host}",
                "Le volume de {host} se remplit vite. Pouvez-vous ajouter de l'espace disque "
                "avant la fin du mois ?",
            ),
            (
                "Création d'un dossier partagé",
                "Merci de créer un dossier partagé « {share} » pour l'équipe, avec des droits "
                "en lecture et écriture pour {n} personnes.",
            ),
        ],
        "information": [
            (
                "Où sont hébergés nos serveurs ?",
                "Pouvez-vous me confirmer où sont hébergés nos serveurs et qui y a accès ? Un "
                "client nous pose la question dans un audit.",
            ),
            (
                "Capacité restante sur {host}",
                "Quelle est la capacité de stockage restante sur {host} ? Nous prévoyons "
                "d'archiver beaucoup de documents cette année.",
            ),
        ],
    },
    "backup": {
        "incident": [
            (
                "Échec de la sauvegarde cette nuit",
                "Nous avons reçu un message indiquant que la sauvegarde de {host} a échoué "
                "cette nuit. Pouvez-vous vérifier que nos données sont bien protégées ?",
            ),
            (
                "Impossible de restaurer un fichier",
                "J'essaie de récupérer un fichier depuis la sauvegarde mais la restauration "
                "reste bloquée à 0 % {since}.",
            ),
        ],
        "service_request": [
            (
                "Restauration d'un dossier supprimé",
                "J'ai supprimé par erreur le dossier {share} hier en fin de journée. Pouvez-vous "
                "le restaurer depuis la sauvegarde ?",
            ),
            (
                "Ajout d'un dossier à la sauvegarde",
                "Merci d'ajouter le dossier {share} aux sauvegardes automatiques, il n'y est "
                "pas encore.",
            ),
        ],
        "information": [
            (
                "Durée de conservation des sauvegardes",
                "Combien de temps conservez-vous nos sauvegardes ? Notre assureur nous demande "
                "cette information.",
            ),
            (
                "Fréquence des sauvegardes",
                "À quelle fréquence {host} est-il sauvegardé, et où sont stockées les copies ?",
            ),
        ],
    },
    "security": {
        "incident": [
            (
                "Mail suspect reçu, j'ai cliqué sur le lien",
                "J'ai reçu un mail qui semblait venir de la banque et j'ai cliqué sur le lien "
                "avant de me méfier. Je n'ai rien saisi mais mon poste se comporte bizarrement.",
            ),
            (
                "Alerte antivirus sur mon poste",
                "L'antivirus affiche une alerte rouge sur mon {device} {since} et me demande de "
                "contacter l'administrateur. Dois-je éteindre la machine ?",
            ),
            (
                "Fichiers renommés avec une extension inconnue",
                "Plusieurs fichiers du dossier {share} ont une extension étrange et on ne peut "
                "plus les ouvrir. Il y a aussi un fichier texte qui réclame de l'argent.",
            ),
        ],
        "service_request": [
            (
                "Analyse d'un mail douteux",
                "Pouvez-vous analyser un mail reçu par {colleague} avant qu'elle ne l'ouvre ? "
                "Je vous le transfère en pièce jointe.",
            ),
            (
                "Installation de l'antivirus sur un nouveau poste",
                "Merci d'installer l'antivirus de l'entreprise sur le {device} de {colleague}, "
                "arrivé ce matin.",
            ),
        ],
        "information": [
            (
                "Sensibilisation au hameçonnage",
                "Proposez-vous une session de sensibilisation à la sécurité pour nos équipes ? "
                "Nous avons {n} personnes à former.",
            ),
            (
                "Sommes-nous concernés par cette faille ?",
                "J'ai lu un article sur une faille touchant les pare-feu. Sommes-nous concernés "
                "et devons-nous faire quelque chose ?",
            ),
        ],
    },
    "telephony": {
        "incident": [
            (
                "Plus de tonalité sur les téléphones fixes",
                "Les téléphones fixes de {site} n'ont plus de tonalité {since}. Les appels "
                "entrants tombent sur messagerie.",
            ),
            (
                "Plus de réseau sur {phone_model}",
                "Mon {phone_model} n'a plus de réseau mobile {since} alors que mes collègues "
                "captent normalement.",
            ),
            (
                "Mauvaise qualité des appels",
                "Les appels sont hachés et on entend de l'écho {since}. Les clients se "
                "plaignent de ne pas nous comprendre.",
            ),
        ],
        "service_request": [
            (
                "Programmation d'un nouveau poste téléphonique",
                "Merci de programmer le poste de {colleague} avec le numéro interne 2{n}0 et la "
                "même configuration que le poste voisin.",
            ),
            (
                "Transfert d'appels pendant les congés",
                "Pouvez-vous mettre en place un renvoi des appels du standard vers un mobile du "
                "lundi au vendredi ?",
            ),
        ],
        "information": [
            (
                "Forfait mobile de l'entreprise",
                "Quel est le forfait associé à {phone_model} de {colleague} ? Je voudrais savoir "
                "si les appels vers l'étranger sont inclus.",
            ),
            (
                "Portabilité de notre numéro",
                "Que faut-il prévoir pour conserver notre numéro de standard si nous changeons "
                "d'opérateur ?",
            ),
        ],
    },
    "procurement": {
        "incident": [
            (
                "Commande reçue incomplète",
                "La livraison de ce matin ne contient pas tout ce qui était prévu : il manque "
                "{item} par rapport au bon de commande.",
            ),
            (
                "Matériel arrivé endommagé",
                "{item} est arrivé avec le carton écrasé et ne s'allume pas. Pouvez-vous gérer "
                "un échange avec le fournisseur ?",
            ),
        ],
        "service_request": [
            (
                "Demande de devis pour {item}",
                "Pouvez-vous nous faire un devis pour {qty} unités de {item} ? Nous souhaitons "
                "décider avant la fin du mois.",
            ),
            (
                "Commande de matériel pour un nouvel arrivant",
                "Merci de commander {item} et une souris pour {colleague}, qui arrive le "
                "mois prochain.",
            ),
        ],
        "information": [
            (
                "Délai de livraison pour {item}",
                "Quel est le délai habituel pour recevoir {item} ? Nous préparons un "
                "déménagement et devons anticiper.",
            ),
            (
                "Garantie sur notre matériel",
                "Pouvez-vous me dire jusqu'à quand {item} acheté chez vous est sous garantie ?",
            ),
        ],
    },
    "admin_billing": {
        "incident": [
            (
                "Erreur sur la facture {invoice}",
                "La facture {invoice} de {month} indique {amount} alors que nous avions convenu "
                "d'un autre tarif. Pouvez-vous la corriger ?",
            ),
            (
                "Facture reçue en double",
                "Nous avons reçu deux fois la facture {invoice}, et le prélèvement a été fait "
                "deux fois sur notre compte.",
            ),
        ],
        "service_request": [
            (
                "Changement d'adresse de facturation",
                "Notre société a déménagé. Merci de mettre à jour l'adresse de facturation sur "
                "le contrat {contract} à partir du mois prochain.",
            ),
            (
                "Demande de copie de facture",
                "Pouvez-vous nous renvoyer la facture {invoice} ? Notre comptable ne la retrouve "
                "pas.",
            ),
            (
                "Résiliation d'une prestation",
                "Nous souhaitons mettre fin à la prestation du contrat {contract}. Quelle est la "
                "procédure et quel préavis faut-il respecter ?",
            ),
        ],
        "information": [
            (
                "Question sur le détail de notre contrat",
                "Que comprend exactement le contrat {contract} ? Je voudrais savoir si les "
                "interventions sur site sont incluses.",
            ),
            (
                "Date d'échéance de notre contrat",
                "Pouvez-vous m'indiquer la date de fin du contrat {contract} et les conditions "
                "de reconduction ?",
            ),
        ],
    },
}

# --------------------------------------------------------------------------- phrasing

GREETINGS = {
    "email": ("Bonjour,", "Bonjour l'équipe,", "Bonjour à tous,", "Bonsoir,", "Hello,"),
    "internal": ("Salut,", "Coucou l'équipe,", "Hello,", "Bonjour,"),
    "portal": ("",),
}

CLOSINGS = (
    "Cordialement,",
    "Bien cordialement,",
    "Merci d'avance,",
    "Merci pour votre aide,",
    "Bonne journée,",
)

# Urgency sentence by priority (more urgent = stronger wording).
URGENCY = {
    "P1": (
        "C'est très urgent, toute l'entreprise est à l'arrêt.",
        "Nous sommes complètement bloqués, c'est critique, merci d'intervenir tout de suite.",
        "Aucun de nos salariés ne peut travailler, il faut agir immédiatement.",
    ),
    "P2": (
        "Plusieurs personnes sont bloquées, pouvez-vous regarder rapidement ?",
        "C'est assez urgent, nous en avons besoin aujourd'hui.",
        "Cela pénalise fortement notre activité, merci de traiter en priorité.",
    ),
    "P3": (
        "Cela nous gêne mais nous pouvons contourner pour le moment.",
        "Merci de regarder cela dans la journée ou demain.",
        "Pas de blocage total, mais ce serait bien de régler ça cette semaine.",
    ),
    "P4": (
        "Aucune urgence, quand vous aurez un moment.",
        "Ce n'est pas pressé, simple demande pour la suite.",
        "À traiter quand vous pourrez, rien de bloquant.",
    ),
}

# Message on a ticket already open: nothing new, or a worsened situation.
LINKED_INTRO = (
    "Suite à mon ticket {ref} : ",
    "Je reviens vers vous au sujet du ticket {ref} : ",
    "Complément pour {ref} : ",
    "Concernant le ticket {ref}, ",
)
LINKED_CALM = (
    "pas de changement de mon côté, je voulais juste ajouter une précision.",
    "je vous confirme que le problème est toujours là, sans changement.",
    "voici un complément d'information, sans urgence particulière.",
)
LINKED_ESCALATION = (
    "la situation s'est aggravée depuis mon premier message, c'est devenu bloquant pour {n} "
    "personnes.",
    "j'ai un rendez-vous client important demain et j'en ai absolument besoin d'ici là.",
    "ce n'est plus supportable, nous perdons du temps chaque heure. Pouvez-vous accélérer ?",
)

SECRET_SENTENCES = (
    "Mon mot de passe actuel est {secret}, si cela peut vous aider.",
    "Voici le code d'accès que j'utilise : {secret}.",
    "La clé fournie par l'éditeur est {secret}.",
)

CONTACT_SENTENCES = (
    "Vous pouvez me joindre au {phone}.",
    "Mon numéro direct : {phone}, mon adresse : {email}.",
    "Répondez-moi directement à {email}.",
)

SUBJECT_PREFIXES_URGENT = ("URGENT - ", "URGENT : ", "[URGENT] ", "!!! ")

# --------------------------------------------------------------------------- alerts

# category -> [(check name, plain-text output), ...]. Check names use the English
# wording of the tools (Zabbix templates, Centreon plugins). Categories absent from
# the keywords of ``monitoring_check_category``, and a few checks of other categories
# that contain no keyword ("unmatched" checks), exercise the "no rule matches" path.
# The generator verifies every entry against the taxonomy.
ALERT_CHECKS: dict[str, list[tuple[str, str]]] = {
    "infrastructure": [
        ("Free disk space is less than 10% on volume C:", "Free space: {pct}% ({gb} GB left)"),
        ("Free disk space is less than 5% on volume D:", "Free space: {pct}% ({gb} GB left)"),
        ("High CPU utilization (over 90% for 5m)", "CPU utilization: {pct}%"),
        ("Lack of available memory (less than 5%)", "Available memory: {pct}%"),
        ("Windows service is not running (Spooler)", "Service state: stopped"),
        ("Host has been restarted (uptime < 10m)", "Uptime: {n} seconds"),
        ("VM snapshot older than 3 days", "Snapshot age: {n} days"),
        ("Datastore free space below 15%", "Free space: {pct}%"),
        # Directory check with no taxonomy keyword: exercises the "no rule" path.
        ("LDAP bind time above threshold", "Bind time: {n}00 ms"),
    ],
    "network": [
        ("Interface Gi0/{n}: link down", "Interface Gi0/{n} operational status: down"),
        ("WAN link: high latency", "Latency: {n} ms (threshold 150 ms)"),
        ("VPN tunnel is down", "Tunnel state: down since {n} minutes"),
        ("Ping loss is too high", "Packet loss: {pct}%"),
        ("Firewall: high session count", "Sessions: {n}00 (threshold 1000)"),
        ("Wifi access point not responding", "No response for {n} minutes"),
        ("Switch stack member missing", "Members found: 1 of 2"),
    ],
    "backup": [
        ("Backup job failed", "Last result: failed, error code 0x{n}"),
        ("Backup older than 36 hours", "Last success: {n} hours ago"),
        ("Sauvegarde nocturne en échec", "Dernier résultat : échec, code {n}"),
        ("Replication lag is too high", "Lag: {n} minutes"),
    ],
    "security": [
        ("Antivirus definitions are out of date", "Definitions age: {n} days"),
        ("EDR agent is disconnected", "Last seen: {n} hours ago"),
        ("Malware detected on endpoint", "Threat quarantined: Trojan.Generic.{n}"),
        ("Ransomware behaviour detected", "Process blocked, {n} files touched"),
        # Brute force suspected: security by default (decision of 2026-10-21).
        ("Too many failed logons", "Failed logons in 10 minutes: {n}0"),
    ],
    "printing": [
        ("Printer is offline", "No SNMP response for {n} minutes"),
        ("Toner level is low (below 10%)", "Black toner: {pct}%"),
        ("Printer paper jam", "Error code 13.{n}"),
    ],
    # Unmatched checks: no keyword of the taxonomy appears in their name (also: LDAP above).
    "messaging": [
        ("Mail queue length is too high", "Queue length: {n}00 messages"),
        ("Certificate expires in less than 14 days (OWA)", "Days left: {n}"),
    ],
    "accounts": [
        # A single account locked out (low volume): an account issue, not an attack.
        ("Domain account locked out", "Locked accounts in the last hour: 1 ({n} failed attempts)"),
    ],
    "software": [
        ("Licence usage above 95%", "Licences used: {pct}%"),
        ("Application pool recycled unexpectedly", "Recycles in the last hour: {n}"),
    ],
    "workstation": [
        ("Windows update pending for more than 30 days", "Pending updates: {n}"),
        ("SMART pre-failure warning on workstation drive", "Reallocated sectors: {n}0"),
    ],
}

# Host-level Centreon check (host states DOWN / UNREACHABLE): contains "ping".
CENTREON_HOST_CHECK = ("Host-Alive (ping)", "CRITICAL - {ip}: rta nan, lost 100%")

"""100 % fictitious identities and technical values.

Everything produced here is recognisable on purpose, so that pseudonymisation
tests can find it and nothing can be mistaken for real personal data:

- e-mail domains end with ``.test`` (reserved by RFC 2606, never resolvable);
- IP addresses come from the documentation ranges of RFC 5737;
- phone numbers use the ranges reserved for fiction by the French regulator
  (ARCEP): ``01 99 00 xx xx`` and ``06 39 98 xx xx``;
- company and family names are invented (none is meant to exist);
- "secrets" all contain the marker ``FAKE``.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass

EMAIL_DOMAIN_SUFFIX = ".test"
DOCUMENTATION_IP_PREFIXES = ("192.0.2.", "198.51.100.", "203.0.113.")
FICTIVE_PHONE_PREFIXES = ("01 99 00", "06 39 98")
SECRET_MARKER = "FAKE"

FIRST_NAMES = (
    "Camille", "Julien", "Sophie", "Nicolas", "Élodie", "Thomas", "Marion", "Antoine",
    "Laure", "Maxime", "Claire", "Romain", "Inès", "Hugo", "Manon", "Pierre", "Chloé",
    "Alexandre", "Léa", "Mathieu", "Sarah", "Vincent", "Julie", "Damien", "Emma", "Baptiste",
)  # fmt: skip

# Invented family names (not taken from any directory).
LAST_NAMES = (
    "Vaudrelle", "Montferane", "Belcourin", "Tarnaguet", "Lorvenet", "Ostrevane", "Pellanoir",
    "Quesnavel", "Dorbeval", "Marcelande", "Fougerolle", "Hautevenne", "Brisecoeur", "Lanterval",
    "Sombrevoir", "Cravanchet", "Dufresval", "Mirebelaine", "Ventrelac", "Tessonvale",
    "Armorquin", "Bellecombre", "Rochevaine", "Savernoy",
)  # fmt: skip

COMPANY_KINDS = (
    "Cabinet", "Ateliers", "Maison", "Transports", "Boulangerie", "Clinique vétérinaire",
    "Imprimerie", "Bureau d'études", "Menuiserie", "Négoce", "Pharmacie", "Agence",
)  # fmt: skip

# Invented company stems (fantasy words).
COMPANY_STEMS = (
    "Fournilune", "Brumevent", "Tarnavel", "Orsolane", "Quimbrelle", "Vasquenote", "Almerande",
    "Pivoinerie", "Corbelune", "Mortelaine", "Sablevert", "Hirondelune", "Gavelinot", "Pruneval",
    "Estrelune", "Navaroise", "Lucarnet", "Brindelaine", "Cotonade", "Rivelombre", "Fenaison",
    "Tourbillac", "Marjolane", "Ostelune", "Bruyerelle", "Vignelune", "Capelinot", "Ardoisine",
    "Sourcelune", "Moissonade", "Bellevoile", "Tamarelle", "Pontevent", "Granvelune", "Orfevrine",
    "Coquelinot", "Dentelune", "Alizette", "Ribaudelle", "Verdelaine", "Passerelune", "Houblonade",
    "Saugenaie", "Clairevoie", "Tilleulune", "Mandarinet", "Girandole", "Fusainet", "Lavandelune",
    "Ormeaulet", "Pâquerette", "Chevrefine", "Sarrasine", "Noisetelle", "Muscadelune",
    "Cormorane", "Bouleauvent", "Genetelle", "Aubepinet", "Romarinelle", "Zéphyrine",
)  # fmt: skip


def ascii_slug(text: str) -> str:
    """Lowercase ASCII slug usable in a host or domain name."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", stripped.lower()).strip("-")


@dataclass(frozen=True)
class Person:
    """A fictitious employee of a fictitious client."""

    first_name: str
    last_name: str
    email: str
    phone: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass(frozen=True)
class Client:
    """A fictitious client company with its own ``.test`` domain."""

    client_id: str
    name: str
    slug: str
    domain: str
    code: str
    users: tuple[Person, ...]


def fictive_phone(rng: random.Random) -> str:
    prefix = rng.choice(FICTIVE_PHONE_PREFIXES)
    return f"{prefix} {rng.randint(0, 99):02d} {rng.randint(0, 99):02d}"


def fictive_ip(rng: random.Random) -> str:
    return f"{rng.choice(DOCUMENTATION_IP_PREFIXES)}{rng.randint(1, 254)}"


def fictive_secret(rng: random.Random) -> str:
    """A fake secret (password or token), always containing the ``FAKE`` marker."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    token = "".join(rng.choice(alphabet) for _ in range(10))
    kind = rng.choice(("PWD", "TOKEN", "KEY"))
    return f"{SECRET_MARKER}-{kind}-{token}"


def build_clients(rng: random.Random, count: int = 60, users_per_client: int = 6) -> list[Client]:
    """Create ``count`` distinct fictitious clients, each with a few employees."""
    if count > len(COMPANY_STEMS):
        raise ValueError(f"At most {len(COMPANY_STEMS)} distinct clients can be generated")
    stems = rng.sample(COMPANY_STEMS, count)
    clients: list[Client] = []
    for index, stem in enumerate(stems, start=1):
        name = f"{rng.choice(COMPANY_KINDS)} {stem}"
        slug = ascii_slug(stem)
        domain = f"{slug}{EMAIL_DOMAIN_SUFFIX}"
        users: list[Person] = []
        seen: set[str] = set()
        while len(users) < users_per_client:
            first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
            email = f"{ascii_slug(first)}.{ascii_slug(last)}@{domain}"
            if email in seen:
                continue
            seen.add(email)
            users.append(Person(first, last, email, fictive_phone(rng)))
        clients.append(Client(f"C{index:03d}", name, slug, domain, slug[:3].upper(), tuple(users)))
    return clients

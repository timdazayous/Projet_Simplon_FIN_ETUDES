"""One convention for the placeholders and fictitious data of every corpus source (Issue #54).

Before this module, each source wrote its own format: the external test (tasksource) used
``[NAME]``, ``[SERVER]``; the public training tickets used ``<name>``, ``<tel_num>``, ``<br>``,
``[Votre nom]``; the generator wrote fictitious names, e-mail addresses, phone numbers, hosts and
secrets in clear. A model that sees one format only in one source learns the origin of a text, not
its category (see ``docs/donnees/corpus.md``).

Convention: **square brackets, upper case, the tasksource spelling** (the only real source, so the
only one that is kept as it is). ``apply_convention`` rewrites any other source to that format.

| Tag | Meaning |
|---|---|
| ``[NAME]`` | person |
| ``[COMPANY]`` | company |
| ``[LOCATION]`` | place |
| ``[ADDRESS]`` | postal address |
| ``[USERNAME]`` | login |
| ``[TICKET ID]`` | reference of another ticket |
| ``[SERVER]`` | host name |
| ``[EMAIL]`` | e-mail address |
| ``[PHONE]`` | phone number |
| ``[IP]`` | IP address |
| ``[MAC_ADDRESS]`` | MAC address |
| ``[URL]`` | web address |
| ``[SOFTWARE]`` | software name |
| ``[PASSWORD]`` | secret (password, token, key) |
| ``[ACCOUNT_NUMBER]`` | account number |
| ``[IMAGE]`` | image that was in the original message |

``[URGENT]`` (subject prefix written by a person) is not a placeholder and stays as it is.
"""

from __future__ import annotations

import re

from src.data.fictive import COMPANY_KINDS, COMPANY_STEMS, FIRST_NAMES, LAST_NAMES

CONVENTION_TAGS = frozenset(
    {
        "[NAME]",
        "[COMPANY]",
        "[LOCATION]",
        "[ADDRESS]",
        "[USERNAME]",
        "[TICKET ID]",
        "[SERVER]",
        "[EMAIL]",
        "[PHONE]",
        "[IP]",
        "[MAC_ADDRESS]",
        "[URL]",
        "[SOFTWARE]",
        "[PASSWORD]",
        "[ACCOUNT_NUMBER]",
        "[IMAGE]",
    }
)
NOT_A_PLACEHOLDER = frozenset({"[URGENT]"})

# Old spellings found in the sources (counted on the real data, see docs/donnees/corpus.md).
_LEGACY = {
    "<tel_num>": "[PHONE]",
    "<acc_num>": "[ACCOUNT_NUMBER]",
    "<name>": "[NAME]",
    "<nom>": "[NAME]",
    "<email>": "[EMAIL]",
    "<ip>": "[IP]",
    "[votre nom]": "[NAME]",
    "[nom]": "[NAME]",
    "[your name]": "[NAME]",
    "[your company]": "[COMPANY]",
    "[image]": "[IMAGE]",
}
_LEGACY_RE = re.compile("|".join(re.escape(k) for k in _LEGACY), re.IGNORECASE)
_LINE_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
_PHOTO_CREDIT = re.compile(
    r"\[cr.dit photographique\]", re.IGNORECASE
)  # translated "[Photo credit]"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Fictitious data of the generator (src/data/fictive.py): recognisable by construction.
_TICKET_REF = re.compile(r"\[Ticket #\d+\]|#\d{5}")
_PHONE = re.compile(r"(?:01 99 00|06 39 98) \d\d \d\d")
_IP = re.compile(r"\b(?:192\.0\.2|198\.51\.100|203\.0\.113)\.\d{1,3}\b")
_SERVER = re.compile(r"\b[A-Z]{3}-SRV-[A-Z]+\d+\b")
_SECRET = re.compile(r"FAKE-(?:PWD|TOKEN|KEY)-[a-z0-9]+")


def _any_of(words: tuple[str, ...]) -> str:
    return "(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + ")"


_FULL_NAME = re.compile(rf"\b{_any_of(FIRST_NAMES)} {_any_of(LAST_NAMES)}\b")
_LONE_NAME = re.compile(rf"\b(?:{_any_of(FIRST_NAMES)}|{_any_of(LAST_NAMES)})\b")
_COMPANY = re.compile(rf"\b(?:{_any_of(COMPANY_KINDS)} )?{_any_of(COMPANY_STEMS)}\b")


def apply_convention(text: str, *, fictitious: bool = False) -> str:
    """Rewrite ``text`` in the project convention.

    ``fictitious=True`` is for generator texts: the fictitious data written in clear (names,
    companies, phone numbers, addresses, hosts, secrets, ticket numbers) become tags. Real
    sources only get their old tag spellings replaced (a first name found in a real text must not
    be touched: it is already masked by the source, and it could be a common word).
    """
    text = _LINE_BREAK.sub("\n", text)
    text = _PHOTO_CREDIT.sub("[IMAGE]", text)
    text = _LEGACY_RE.sub(lambda m: _LEGACY[m.group(0).lower()], text)
    text = _EMAIL.sub("[EMAIL]", text)
    if fictitious:
        text = _TICKET_REF.sub("[TICKET ID]", text)
        text = _PHONE.sub("[PHONE]", text)
        text = _IP.sub("[IP]", text)
        text = _SERVER.sub("[SERVER]", text)
        text = _SECRET.sub("[PASSWORD]", text)
        text = _COMPANY.sub("[COMPANY]", text)
        text = _FULL_NAME.sub("[NAME]", text)
        text = _LONE_NAME.sub("[NAME]", text)
    return text


_SQUARE = re.compile(r"\[[^\]\n]{1,40}\]")
_ANGLE = re.compile(r"<[A-Za-z_]{1,20}>")


def leftover_tags(text: str) -> list[str]:
    """Tag-like tokens that are not in the convention (old spellings, clear e-mail addresses...)."""
    found = [
        token
        for token in _SQUARE.findall(text)
        if token not in CONVENTION_TAGS and token not in NOT_A_PLACEHOLDER
    ]
    found += _ANGLE.findall(text)
    found += _EMAIL.findall(text)
    found += re.findall(r"\[Ticket #\d+\]", text)
    found += _SECRET.findall(text)
    return found


def count_tags(texts: list[str]) -> dict[str, int]:
    """Number of occurrences of each convention tag (counts only, for the report)."""
    counts: dict[str, int] = {}
    for text in texts:
        for token in _SQUARE.findall(text):
            if token in CONVENTION_TAGS:
                counts[token] = counts.get(token, 0) + 1
    return dict(sorted(counts.items()))

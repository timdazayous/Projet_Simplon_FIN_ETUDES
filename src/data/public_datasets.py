"""Fetch, check, clean and sample the public ticket datasets (Issue #29, phase 1).

Steps of :func:`run_fetch`: initialise (read the configuration), check the licence on the
Hugging Face card (refuse if it differs), download, read, clean and filter, sample with a
fixed seed, attach the label proposal, save JSONL under ``data/raw/public/`` (ignored by Git).

Network access and file formats are isolated (``HubClient``, ``read_rows``) so that the tests
run without any download.
"""

from __future__ import annotations

import csv
import json
import random
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from src.data.label_mapping import LabelMapping

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "public_datasets.yaml"


class LicenseError(RuntimeError):
    """The licence found on the Hugging Face card is not the expected one."""


# --------------------------------------------------------------------------- configuration


@dataclass(frozen=True)
class DatasetSpec:
    """One dataset of ``config/public_datasets.yaml``."""

    name: str
    repo_id: str
    expected_license: str
    role: str
    id_prefix: str
    format: str
    files: tuple[str, ...]
    languages: tuple[str, ...]
    language_source: str
    min_chars: int
    max_chars: int
    attribution: str
    max_records: int | None = None
    queues: tuple[str, ...] = ()
    label_names: tuple[str, ...] = ()
    strip_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PublicConfig:
    seed: int
    output_directory: Path
    cache_directory: Path
    datasets: dict[str, DatasetSpec]
    translation_models: dict[str, dict[str, str]] = field(default_factory=dict)


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> PublicConfig:
    """Read the configuration file (relative paths are relative to the repository root)."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    root = Path(__file__).resolve().parents[2]
    datasets = {}
    for name, d in raw["datasets"].items():
        datasets[name] = DatasetSpec(
            name=name,
            repo_id=d["repo_id"],
            expected_license=d["expected_license"],
            role=d["role"],
            id_prefix=d["id_prefix"],
            format=d["format"],
            files=tuple(d["files"]),
            languages=tuple(d["languages"]),
            language_source=d["language_source"],
            min_chars=d["min_chars"],
            max_chars=d["max_chars"],
            attribution=" ".join(d["attribution"].split()),
            max_records=d.get("max_records"),
            queues=tuple(d.get("queues", ())),
            label_names=tuple(d.get("label_names", ())),
            strip_prefixes=tuple(d.get("strip_prefixes", ())),
        )
    return PublicConfig(
        seed=raw["seed"],
        output_directory=root / raw["output_directory"],
        cache_directory=root / raw["cache_directory"],
        datasets=datasets,
        translation_models=raw.get("translation_models", {}),
    )


# --------------------------------------------------------------------------- licence + hub


def check_license(spec: DatasetSpec, actual: str | None) -> None:
    """Refuse the dataset if the card licence differs from the expected one."""
    if (actual or "").strip().lower() != spec.expected_license.lower():
        raise LicenseError(
            f"{spec.repo_id}: licence '{actual}' found on the card, "
            f"'{spec.expected_license}' expected. Refusing to download."
        )


class HubClient(Protocol):
    """What the pipeline needs from Hugging Face (replaced by a fake in the tests)."""

    def get_license(self, repo_id: str) -> str | None: ...

    def download(self, repo_id: str, filename: str, cache_dir: Path) -> Path: ...


class HuggingFaceHub:
    """Real client built on ``huggingface_hub`` (group ``data`` of uv)."""

    def get_license(self, repo_id: str) -> str | None:
        from huggingface_hub import HfApi

        info = HfApi().dataset_info(repo_id)
        return info.card_data.license if info.card_data else None

    def download(self, repo_id: str, filename: str, cache_dir: Path) -> Path:
        from huggingface_hub import hf_hub_download

        return Path(
            hf_hub_download(
                repo_id=repo_id, filename=filename, repo_type="dataset", cache_dir=str(cache_dir)
            )
        )


# --------------------------------------------------------------------------- reading


def read_rows(spec: DatasetSpec, path: Path) -> Iterator[dict[str, Any]]:
    """Yield the raw rows of one downloaded file, with its position in ``_row``."""
    if spec.format == "tobi_csv":
        with open(path, encoding="utf-8", newline="") as handle:
            for index, row in enumerate(csv.DictReader(handle), start=1):
                yield {**row, "_row": index, "_file": path.name}
    elif spec.format == "tasksource_parquet":
        import pyarrow.parquet as pq

        table = pq.read_table(path).to_pylist()
        split = "test" if "test" in path.name else "train"
        for index, row in enumerate(table, start=1):
            yield {**row, "_row": index, "_file": path.name, "_split": split}
    elif spec.format == "urgency_jsonl":
        with open(path, encoding="utf-8") as handle:
            for index, line in enumerate(handle, start=1):
                if line.strip():
                    yield {**json.loads(line), "_row": index, "_file": path.name}
    else:
        raise ValueError(f"Unknown format '{spec.format}' for {spec.name}")


# --------------------------------------------------------------------------- cleaning

_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")
_MOJIBAKE = re.compile(r"Ã[\u0080-¿]|Â[\u0080-¿]")


def normalise_text(text: str | None) -> str:
    """Homogenise a text: Unicode NFC, real line breaks, no stray spaces."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\n", "\n")  # the CSV of the customer-support set holds literal "\n"
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", text).strip()


def is_corrupted(text: str) -> bool:
    """Replacement characters or double-encoded accents: the text cannot be trusted."""
    if not text:
        return False
    replacement = text.count("�")
    return replacement > 3 or replacement / len(text) > 0.02 or len(_MOJIBAKE.findall(text)) >= 2


def dedup_key(subject: str, body: str) -> str:
    """Key of the exact-duplicate filter (case and spacing ignored)."""
    return " ".join(f"{subject} {body}".lower().split())


# --------------------------------------------------------------------------- language

# Frequent words, enough to tell English, German, Spanish and Portuguese apart on short texts.
_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        "the and to of is in for on with not you your please my we are can be this that it "
        "have has from at by an or hello thanks thank need cannot cant access new i setup update "
        "install installation software account file share user leaving employee remove reset "
        "issue connecting trouble printer drive external calendar permission mobile phone "
        "password login".split()
    ),
    "de": frozenset(
        "der die das und ist nicht ich wir sie mit für auf ein eine zu den dem im bitte von "
        "bei kann haben wird auch es sich als aus nach über danke hallo mein meine "
        "verschlüsselung benutzer zugriff".split()
    ),
    "es": frozenset(
        "el la los las y es en un una de para con por que no se mi su al del como esta están "
        "favor gracias hola necesito problema puedo tengo acceso impresora ingreso equipo "
        "activacion activación problemas usuario sin puede ingresar".split()
    ),
    "pt": frozenset(
        "o os as e é em um uma de do da dos das para com por que não se meu minha ao como está "
        "favor obrigado obrigada olá preciso problema posso tenho foi acesso usuário cadastrar "
        "conexão telefone erro entrar compra reparos celular pastas servidor cancelamento "
        "acessos instalação impressora".split()
    ),
}
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_PLACEHOLDER = re.compile(r"\[[A-Z _]+\]")
# Accents and letters that exist in only one language of the four.
_DISTINCTIVE = {"de": "äöüß", "pt": "ãõç", "es": "ñ¿¡"}


def detect_language(text: str) -> str | None:
    """Guess ``en``, ``de``, ``es`` or ``pt``; ``None`` if the text is too short or ambiguous.

    A deliberately simple heuristic (stop words and a few distinctive letters), with no extra
    dependency: its accuracy is checked on the sample, see the documentation.
    """
    words = [w.lower() for w in _WORD.findall(_PLACEHOLDER.sub(" ", text))]
    if not words:
        return None
    scores = {
        lang: sum(1 for w in words if w in vocabulary) for lang, vocabulary in _STOPWORDS.items()
    }
    lowered = text.lower()
    for lang, letters in _DISTINCTIVE.items():
        scores[lang] += sum(lowered.count(ch) for ch in letters)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, best_score), (_, second_score) = ranked[0], ranked[1]
    if best_score < 1 or best_score == second_score:
        return None
    return best


# --------------------------------------------------------------------------- normalisation


def _strip_prefixes(text: str, spec: DatasetSpec) -> str:
    for pattern in spec.strip_prefixes:
        text = re.sub(pattern, "", text, count=1)
    return text


def to_record(spec: DatasetSpec, raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a raw row into the common record, or ``None`` if the row is not usable at all.

    Labels are kept as they are in ``original_labels``; the language is the declared one for
    datasets that have a column, ``None`` otherwise (detected later).
    """
    if spec.format == "tobi_csv":
        tags = [raw.get(f"tag_{i}") for i in range(1, 9)]
        return {
            "origin_id": f"{raw['_file']}:{raw['_row']}",
            "split": spec.role,
            "subject": normalise_text(raw.get("subject")),
            "body": normalise_text(raw.get("body")),
            "language_declared": (raw.get("language") or "").strip().lower() or None,
            "queue": raw.get("queue"),
            "original_labels": {
                "queue": raw.get("queue"),
                "type": raw.get("type"),
                "priority": raw.get("priority"),
                "tags": [t.strip() for t in tags if t and t.strip()],
            },
        }
    if spec.format == "tasksource_parquet":
        label = raw.get("label")
        names = spec.label_names
        if not isinstance(label, int) or not 0 <= label < len(names):
            return None
        text = normalise_text(_strip_prefixes(normalise_text(raw.get("text")), spec))
        return {
            "origin_id": f"{raw['_split']}:{raw['_row']}",
            "split": raw["_split"],
            "subject": "",
            "body": text,
            "language_declared": None,
            "queue": None,
            "original_labels": {"label": names[label]},
        }
    if spec.format == "urgency_jsonl":
        return {
            "origin_id": str(raw.get("case_id")),
            "split": raw.get("split") or spec.role,
            "subject": "",
            "body": normalise_text(raw.get("state")),
            "language_declared": (raw.get("language") or "").strip().lower() or None,
            "queue": None,
            "original_labels": {
                "expected": raw.get("expected"),
                "category": raw.get("category"),
                "difficulty": raw.get("difficulty"),
            },
        }
    raise ValueError(f"Unknown format '{spec.format}' for {spec.name}")


# --------------------------------------------------------------------------- filtering


def filter_records(
    spec: DatasetSpec, rows: Iterable[dict[str, Any]]
) -> tuple[list[dict[str, Any]], Counter, Counter]:
    """Apply the cleaning rules in order; return the kept records and the reason counts.

    Reasons: ``queue`` (not an IT queue), ``unreadable`` (row without usable label), ``empty``,
    ``corrupted``, ``too_short``, ``too_long``, ``language`` (not among the dataset languages),
    ``duplicate``. The first reason met wins, so every dropped row is counted once.

    The third value counts corrections that do not drop anything: ``language_corrected`` when
    the declared language of a row contradicts the text (some "de" tickets are in English).
    """
    kept: list[dict[str, Any]] = []
    rejected: Counter = Counter()
    notes: Counter = Counter()
    seen: set[str] = set()
    for raw in rows:
        record = to_record(spec, raw)
        if record is None:
            rejected["unreadable"] += 1
            continue
        if spec.queues and record["queue"] not in spec.queues:
            rejected["queue"] += 1
            continue
        text = f"{record['subject']} {record['body']}".strip()
        if not record["body"]:
            rejected["empty"] += 1
            continue
        if is_corrupted(text):
            rejected["corrupted"] += 1
            continue
        if len(text) < spec.min_chars:
            rejected["too_short"] += 1
            continue
        if len(text) > spec.max_chars:
            rejected["too_long"] += 1
            continue
        detected = detect_language(text)
        language = record["language_declared"] if spec.language_source == "column" else detected
        if spec.language_source == "column" and detected in spec.languages and detected != language:
            language = detected  # the text wins over a wrong label
            notes["language_corrected"] += 1
        if language not in spec.languages:
            rejected["language"] += 1
            continue
        key = dedup_key(record["subject"], record["body"])
        if key in seen:
            rejected["duplicate"] += 1
            continue
        seen.add(key)
        record["language_source"] = language
        kept.append(record)
    return kept, rejected, notes


def sample_records(
    records: list[dict[str, Any]], max_records: int | None, seed: int
) -> list[dict[str, Any]]:
    """Reproducible draw: same seed and same input give the same output."""
    ordered = sorted(records, key=lambda r: r["origin_id"])
    if max_records is None or len(ordered) <= max_records:
        return ordered
    chosen = random.Random(seed).sample(ordered, max_records)
    return sorted(chosen, key=lambda r: r["origin_id"])


def finalise(
    spec: DatasetSpec, records: list[dict[str, Any]], mapping: LabelMapping
) -> list[dict[str, Any]]:
    """Give stable identifiers and attach the label proposal and the licence."""
    final = []
    for number, record in enumerate(records, start=1):
        proposal = mapping.propose(
            spec.name, record["original_labels"], record["subject"], record["body"]
        )
        final.append(
            {
                "id": f"{spec.id_prefix}-{number:05d}",
                "dataset": spec.repo_id,
                "origin_id": record["origin_id"],
                "split": record["split"],
                "role": spec.role,
                "language_source": record["language_source"],
                "subject": record["subject"],
                "body": record["body"],
                "original_labels": record["original_labels"],
                "proposed_labels": proposal.as_dict(),
                "license": spec.expected_license,
                "origin": "public",
            }
        )
    return final


# --------------------------------------------------------------------------- orchestration


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    """Write records to ``path`` atomically (temporary file, then rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    temporary.replace(path)
    return count


def prepare_dataset(
    spec: DatasetSpec,
    files: list[Path],
    mapping: LabelMapping,
    seed: int,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read, clean, sample and label one dataset. Returns the records and a report."""
    rows: list[dict[str, Any]] = []
    for path in files:
        rows.extend(read_rows(spec, path))
    kept, rejected, notes = filter_records(spec, rows)
    target = spec.max_records if limit is None else min(limit, spec.max_records or limit)
    sampled = sample_records(kept, target, seed)
    final = finalise(spec, sampled, mapping)
    report = {
        "dataset": spec.repo_id,
        "license": spec.expected_license,
        "rows_read": len(rows),
        "rejected": dict(rejected),
        "corrections": dict(notes),
        "kept_after_filter": len(kept),
        "kept_after_sampling": len(final),
        "languages": dict(Counter(r["language_source"] for r in final)),
        "proposed_categories": dict(Counter(r["proposed_labels"]["category"] for r in final)),
        "doubtful_proposals": sum(1 for r in final if r["proposed_labels"]["doubtful"]),
    }
    return final, report


def run_fetch(
    config: PublicConfig,
    mapping: LabelMapping,
    hub: HubClient,
    names: list[str] | None = None,
    limit: int | None = None,
    log: Any = print,
) -> dict[str, dict[str, Any]]:
    """Process the datasets one after the other; the first licence mismatch stops everything.

    A network or format error on one dataset is reported and does not erase what was already
    saved for the others.
    """
    reports: dict[str, dict[str, Any]] = {}
    for name in names or list(config.datasets):
        spec = config.datasets[name]
        log(f"[{name}] vérification de la licence de {spec.repo_id}")
        try:
            check_license(spec, hub.get_license(spec.repo_id))  # refuses before any download
            files = []
            for filename in spec.files:
                log(f"[{name}] téléchargement de {filename}")
                files.append(hub.download(spec.repo_id, filename, config.cache_directory))
            records, report = prepare_dataset(spec, files, mapping, config.seed, limit)
        except (OSError, ValueError, KeyError) as error:
            log(f"[{name}] ÉCHEC : {type(error).__name__}: {error}")
            reports[name] = {"error": f"{type(error).__name__}: {error}"}
            continue
        out = config.output_directory / f"{name}_prepared.jsonl"
        report["output"] = str(out)
        report["saved"] = write_jsonl(out, records)
        reports[name] = report
        log(f"[{name}] {report['saved']} tickets enregistrés dans {out}")
    summary = config.output_directory / "prepare_report.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return reports

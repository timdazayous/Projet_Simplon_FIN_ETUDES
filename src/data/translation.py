"""Translate prepared tickets to French with OPUS-MT on CPU, with a memory safety net.

Heavy libraries (torch, transformers) are imported only inside :class:`OpusTranslator`, so this
module can be imported, and tested, without the ``translate`` uv group.

* :class:`MemoryGuard` stops the run cleanly when the system RAM runs low.
* :class:`ResourceMonitor` samples RAM and CPU every 2 s to document the load of the machine.
* :func:`split_text` cuts long tickets into short segments: Marian models translate sentences,
  not pages, and short segments batch better on CPU.
"""

from __future__ import annotations

import json
import re
import statistics
import threading
import time
import zlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MIN_AVAILABLE_MB = 1500  # below this, the run stops (the machine is already loaded)


# --------------------------------------------------------------------------- memory guard


class LowMemoryError(RuntimeError):
    """The available RAM of the system fell under the threshold."""


def _system_available_mb() -> float:
    import psutil

    return psutil.virtual_memory().available / 2**20


class MemoryGuard:
    """Raise :class:`LowMemoryError` when available system RAM is under ``min_available_mb``."""

    def __init__(
        self,
        min_available_mb: float = DEFAULT_MIN_AVAILABLE_MB,
        reader: Callable[[], float] = _system_available_mb,
    ) -> None:
        self.min_available_mb = min_available_mb
        self._reader = reader

    def available_mb(self) -> float:
        return self._reader()

    def check(self, context: str = "") -> None:
        available = self.available_mb()
        if available < self.min_available_mb:
            raise LowMemoryError(
                f"RAM disponible {available:.0f} Mo < seuil {self.min_available_mb:.0f} Mo"
                + (f" ({context})" if context else "")
            )


# --------------------------------------------------------------------------- resource monitor


@dataclass(frozen=True)
class Sample:
    """One measurement: system RAM, RSS of the process tree and CPU shares (0 to 100)."""

    available_mb: float
    process_rss_mb: float
    system_cpu: float
    process_cpu: float  # share of the whole machine (all cores = 100)


def _psutil_sampler() -> Callable[[], Sample]:
    import psutil

    process = psutil.Process()
    cores = psutil.cpu_count(logical=True) or 1
    psutil.cpu_percent(None)  # the first call only starts the counter
    process.cpu_percent(None)

    def sample() -> Sample:
        return Sample(
            available_mb=psutil.virtual_memory().available / 2**20,
            process_rss_mb=process.memory_info().rss / 2**20,
            system_cpu=psutil.cpu_percent(None),
            process_cpu=process.cpu_percent(None) / cores,
        )

    return sample


class ResourceMonitor:
    """Background thread that samples the machine every ``interval`` seconds."""

    def __init__(self, interval: float = 2.0, sampler: Callable[[], Sample] | None = None) -> None:
        self.interval = interval
        self._sampler = sampler
        self.samples: list[Sample] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        if self._sampler is None:
            self._sampler = _psutil_sampler()
        while not self._stop.wait(self.interval):
            self.samples.append(self._sampler())

    def __enter__(self) -> ResourceMonitor:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def summary(self) -> dict[str, float]:
        """Minimum available RAM, peak RSS, mean and peak CPU. Empty dict without a sample."""
        if not self.samples:
            return {}
        return {
            "samples": len(self.samples),
            "min_available_ram_mb": round(min(s.available_mb for s in self.samples)),
            "max_process_rss_mb": round(max(s.process_rss_mb for s in self.samples)),
            "mean_system_cpu_pct": round(statistics.fmean(s.system_cpu for s in self.samples), 1),
            "max_system_cpu_pct": round(max(s.system_cpu for s in self.samples), 1),
            "mean_process_cpu_pct": round(statistics.fmean(s.process_cpu for s in self.samples), 1),
            "max_process_cpu_pct": round(max(s.process_cpu for s in self.samples), 1),
        }


# --------------------------------------------------------------------------- segmentation

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_text(text: str, max_chars: int = 400) -> list[tuple[str, str]]:
    """Cut ``text`` into ``(segment, separator)`` pairs; joining them gives back the text.

    Cuts at line breaks first, then after sentence-ending punctuation, then at spaces for the
    rare sentence longer than ``max_chars``.
    """
    pieces: list[tuple[str, str]] = []
    lines = text.split("\n")
    for index, line in enumerate(lines):
        separator = "\n" if index < len(lines) - 1 else ""
        sentences = _SENTENCE_END.split(line) if line.strip() else [line]
        # Re-find the exact whitespace used between sentences to keep the text intact.
        spaces = _SENTENCE_END.findall(line)
        for number, sentence in enumerate(sentences):
            tail = spaces[number] if number < len(spaces) else ""
            for chunk, chunk_tail in _wrap(sentence, max_chars):
                pieces.append((chunk, chunk_tail or tail))
        if pieces:
            last_segment, last_tail = pieces[-1]
            pieces[-1] = (last_segment, last_tail + separator)
    return pieces


def _wrap(sentence: str, max_chars: int) -> list[tuple[str, str]]:
    if len(sentence) <= max_chars:
        return [(sentence, "")]
    parts, current = [], ""
    for word in sentence.split(" "):
        if current and len(current) + 1 + len(word) > max_chars:
            parts.append((current, " "))
            current = word
        else:
            current = f"{current} {word}" if current else word
    parts.append((current, ""))
    return parts


# Masking tags of the public datasets ("[NAME]", "[TICKET ID]"...). Left as they are, the model
# translates them ("[NOM]", "[IDET TICKET]"); replaced by an opaque code, they come back intact.
_MASK_TAG = re.compile(r"\[([A-Z][A-Z0-9 _]*)\]")
_MASK_CODE = re.compile(r"ZZ(\d{3})\d?ZZ")  # the model sometimes adds a digit: ZZ7999ZZ
_LEFTOVER_CODE = re.compile(r"ZZ\d+ZZ")


# Tags seen in the public datasets get a fixed code (no collision by construction); any other
# tag gets a code derived from its name, in a separate range.
_KNOWN_TAGS = (
    "NAME COMPANY LOCATION ADDRESS USERNAME TICKET_ID SERVER EMAIL SOFTWARE PHONE URL IP PASSWORD "
    "MAC_ADDRESS IP_ADDRESS ID"
).split()


def _code(tag: str) -> str:
    key = tag.replace(" ", "_")
    if key in _KNOWN_TAGS:
        return f"ZZ{100 + _KNOWN_TAGS.index(key)}ZZ"
    return f"ZZ{zlib.crc32(tag.encode()) % 700 + 200}ZZ"


def mask_tags(text: str) -> tuple[str, dict[str, str]]:
    """Replace each ``[TAG]`` by an opaque code; return the new text and the code -> tag table."""
    table: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        code = _code(match.group(1))
        table[code] = match.group(0)
        return code

    return _MASK_TAG.sub(replace, text), table


def unmask_tags(text: str, table: dict[str, str]) -> str:
    """Put the original ``[TAG]`` back in place of the codes."""
    return _MASK_CODE.sub(lambda m: table.get(f"ZZ{m.group(1)}ZZ", m.group(0)), text)


def has_leftover_code(text: str) -> bool:
    """True if a masking code was damaged by the model and could not be restored."""
    return bool(_LEFTOVER_CODE.search(text))


# --------------------------------------------------------------------------- glossary

DEFAULT_GLOSSARY_PATH = Path(__file__).resolve().parents[2] / "config" / "translation_glossary.yaml"
_GLOSSARY_FIRST_CODE = 900  # codes ZZ900ZZ to ZZ999ZZ: no clash with the tag codes (100 to 899)
_GLOSSARY_MAX_TERMS = 100


@dataclass(frozen=True)
class GlossaryTerm:
    """One protected term: kept as written, or replaced by a fixed French wording (``fr``)."""

    term: str
    fr: str | None = None
    ignore_case: bool = False

    @property
    def restored(self) -> str:
        return self.fr if self.fr is not None else self.term


class Glossary:
    """Technical terms that OPUS-MT mistranslates ("Light User", "Active Directory"...).

    Same mechanism as the ``[NAME]`` tags: the term is replaced by an opaque code before
    translation and put back afterwards, as written in the glossary file (or as its fixed French
    wording). Matching respects word boundaries and, unless ``ignore_case``, the case.
    """

    def __init__(self, terms: list[GlossaryTerm]) -> None:
        if len(terms) > _GLOSSARY_MAX_TERMS:
            raise ValueError(f"The glossary holds at most {_GLOSSARY_MAX_TERMS} terms")
        self.terms = terms
        # Longest first, so that "File Share Access" wins over "File Share".
        order = sorted(range(len(terms)), key=lambda i: len(terms[i].term), reverse=True)
        parts = []
        for i in order:
            flag = "i" if terms[i].ignore_case else "-i"
            parts.append(f"(?P<t{i}>(?{flag}:{re.escape(terms[i].term)}))")
        self._pattern = re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)") if parts else None

    @staticmethod
    def code(index: int) -> str:
        return f"ZZ{_GLOSSARY_FIRST_CODE + index}ZZ"

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        """Replace every term by its code; return the new text and the code -> wording table."""
        table: dict[str, str] = {}
        if self._pattern is None:
            return text, table

        def replace(match: re.Match[str]) -> str:
            index = int(match.lastgroup[1:])  # type: ignore[index]
            code = self.code(index)
            table[code] = self.terms[index].restored
            return code

        return self._pattern.sub(replace, text), table


def load_glossary(path: str | Path = DEFAULT_GLOSSARY_PATH) -> Glossary:
    """Read the glossary file (``terms``: list of ``{term, fr?, ignore_case?}``)."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    terms = [
        GlossaryTerm(
            term=str(entry["term"]),
            fr=entry.get("fr"),
            ignore_case=bool(entry.get("ignore_case", False)),
        )
        for entry in raw.get("terms", [])
    ]
    seen: set[str] = set()
    for t in terms:
        key = t.term if not t.ignore_case else t.term.lower()
        if key in seen:
            raise ValueError(f"Glossary term listed twice: '{t.term}'")
        seen.add(key)
    return Glossary(terms)


def translate_texts(
    texts: list[str],
    language: str,
    translate_segments: Callable[[str, list[str]], list[str]],
    glossary: Glossary | None = None,
) -> list[str]:
    """Translate several texts at once (one batch call for all their segments).

    Glossary terms and masking tags are protected, blank segments and separators are kept as
    they are.
    """
    masked = []
    for text in texts:
        if glossary is not None:
            text, glossary_table = glossary.mask(text)
        else:
            glossary_table = {}
        text, tag_table = mask_tags(text)
        masked.append((text, {**glossary_table, **tag_table}))
    split = [split_text(m) for m, _ in masked]
    to_translate = sorted(
        {
            seg
            for pieces in split
            for seg, _ in pieces
            if re.search(r"[^\W\d_]", _MASK_CODE.sub("", seg))
        },
        key=len,
    )
    translated = dict(zip(to_translate, translate_segments(language, to_translate), strict=True))
    return [
        unmask_tags("".join(translated.get(seg, seg) + sep for seg, sep in pieces), table)
        for pieces, (_, table) in zip(split, masked, strict=True)
    ]


# --------------------------------------------------------------------------- translator


class OpusTranslator:
    """OPUS-MT translation on CPU. One model is kept in memory at a time."""

    def __init__(
        self,
        models: dict[str, dict[str, str]],
        guard: MemoryGuard,
        threads: int = 4,
        batch_size: int = 8,
        num_beams: int = 2,
    ) -> None:
        self.models = models
        self.guard = guard
        self.threads = threads
        self.batch_size = batch_size
        self.num_beams = num_beams
        self._language: str | None = None
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self.revisions: dict[str, str] = {}
        self.load_seconds: dict[str, float] = {}

    def _load(self, language: str) -> None:
        if self._language == language:
            return
        self.unload()
        if language not in self.models:
            raise ValueError(f"No translation model configured for language '{language}'")
        self.guard.check("avant le chargement du modèle")
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        started = time.perf_counter()
        torch.set_num_threads(self.threads)
        repo_id = self.models[language]["repo_id"]
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(repo_id)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(repo_id).eval()
        self._language = language
        self.load_seconds[language] = round(time.perf_counter() - started, 1)
        self.revisions[language] = self._revision(repo_id)
        self.guard.check("après le chargement du modèle")

    @staticmethod
    def _revision(repo_id: str) -> str:
        """Commit of the model used (for the report); empty if the Hub cannot be reached."""
        try:
            from huggingface_hub import HfApi

            return HfApi().model_info(repo_id).sha or ""
        except Exception:  # the report is informative, a network error must not stop the run
            return ""

    def unload(self) -> None:
        import gc

        self._tokenizer = self._model = None
        self._language = None
        gc.collect()

    def translate(self, language: str, segments: list[str]) -> list[str]:
        """Translate short segments (already sorted by length) in small batches."""
        self._load(language)
        prefix = self.models[language].get("prefix", "")
        output: list[str] = []
        for start in range(0, len(segments), self.batch_size):
            self.guard.check(f"lot {start // self.batch_size + 1}")
            batch = [prefix + s for s in segments[start : start + self.batch_size]]
            encoded = self._tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=256
            )
            with self._torch.inference_mode():
                generated = self._model.generate(
                    **encoded, num_beams=self.num_beams, max_new_tokens=256, max_length=None
                )
            output.extend(self._tokenizer.batch_decode(generated, skip_special_tokens=True))
        return output


# --------------------------------------------------------------------------- pipeline


def translate_records(
    records: list[dict[str, Any]],
    translate_segments: Callable[[str, list[str]], list[str]],
    guard: MemoryGuard,
    sink: Callable[[list[dict[str, Any]]], None],
    models: dict[str, dict[str, str]],
    chunk_size: int = 10,
    log: Callable[[str], None] = print,
    glossary: Glossary | None = None,
) -> dict[str, Any]:
    """Translate ``records`` language by language, in chunks, saving each chunk through ``sink``.

    Stops cleanly (``status`` = ``"stopped_low_memory"``) if the guard trips: what was already
    saved stays saved. Returns timing and volume figures per language.
    """
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_language[record["language_source"]].append(record)

    stats: dict[str, Any] = {"status": "ok", "languages": {}}
    started = time.perf_counter()
    for language, group in by_language.items():
        lang_start = time.perf_counter()
        done = chars = flagged = 0
        try:
            for start in range(0, len(group), chunk_size):
                chunk = group[start : start + chunk_size]
                guard.check(f"langue {language}")
                subjects = translate_texts(
                    [r["subject"] for r in chunk], language, translate_segments, glossary
                )
                bodies = translate_texts(
                    [r["body"] for r in chunk], language, translate_segments, glossary
                )
                translated = [
                    {
                        **r,
                        "subject_fr": s,
                        "body_fr": b,
                        "translation_model": models[language]["repo_id"],
                        "translation_flags": (
                            ["tag_not_restored"] if has_leftover_code(f"{s} {b}") else []
                        ),
                    }
                    for r, s, b in zip(chunk, subjects, bodies, strict=True)
                ]
                flagged += sum(1 for r in translated if r["translation_flags"])
                sink(translated)
                done += len(chunk)
                chars += sum(len(r["subject"]) + len(r["body"]) for r in chunk)
                log(f"  {language} : {done}/{len(group)}")
        except LowMemoryError as error:
            stats["status"] = "stopped_low_memory"
            stats["reason"] = str(error)
            log(f"ARRÊT : {error}")
        finally:
            seconds = time.perf_counter() - lang_start
            stats["languages"][language] = {
                "tickets": done,
                "chars": chars,
                "flagged": flagged,
                "seconds": round(seconds, 1),
            }
        if stats["status"] != "ok":
            break
    stats["total_seconds"] = round(time.perf_counter() - started, 1)
    stats["total_tickets"] = sum(v["tickets"] for v in stats["languages"].values())
    return stats


def select_mixed_sample(
    records: list[dict[str, Any]], limit: int, seed: int
) -> list[dict[str, Any]]:
    """Take ``limit`` records spread over the languages present (round robin, seeded)."""
    import random

    rng = random.Random(seed)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in sorted(records, key=lambda r: r["id"]):
        groups[record["language_source"]].append(record)
    for group in groups.values():
        rng.shuffle(group)
    chosen: list[dict[str, Any]] = []
    while len(chosen) < limit and any(groups.values()):
        for language in sorted(groups):
            if groups[language] and len(chosen) < limit:
                chosen.append(groups[language].pop())
    return chosen


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def translate_file(
    source: Path,
    target: Path,
    report_path: Path,
    models: dict[str, dict[str, str]],
    glossary: Glossary | None,
    *,
    seed: int,
    limit: int | None = None,
    resume: bool = False,
    threads: int = 4,
    batch_size: int = 8,
    beams: int = 2,
    min_ram_mb: float = DEFAULT_MIN_AVAILABLE_MB,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Translate one prepared JSONL file into ``target`` and write the timing report.

    ``resume`` keeps the tickets already present in ``target``; otherwise ``target`` is replaced.
    Returns the statistics (``status`` is ``ok`` or ``stopped_low_memory``). Needs the uv group
    ``translate`` (torch and transformers are imported by :class:`OpusTranslator`).
    """
    records = read_jsonl(source)
    if limit:
        records = select_mixed_sample(records, limit, seed)
    already_done = 0
    if resume and target.exists():
        done = {r["id"] for r in read_jsonl(target)}
        already_done = len(done)
        records = [r for r in records if r["id"] not in done]
    elif target.exists():
        target.unlink()  # a fresh run replaces the previous output
    log(f"{len(records)} tickets à traduire ({already_done} déjà faits), {threads} threads")

    guard = MemoryGuard(min_ram_mb)
    guard.check("avant le démarrage")
    translator = OpusTranslator(models, guard, threads, batch_size, beams)
    with ResourceMonitor(interval=2.0) as monitor:
        stats = translate_records(
            records,
            translator.translate,
            guard,
            lambda chunk: append_jsonl(target, chunk),
            models,
            log=log,
            glossary=glossary,
        )
    stats["resources"] = monitor.summary()
    stats["settings"] = {
        "threads": threads,
        "batch_size": batch_size,
        "beams": beams,
        "min_ram_mb": min_ram_mb,
        "glossary_terms": len(glossary.terms) if glossary else 0,
        "resume": resume,
        "already_done": already_done,
    }
    stats["model_revisions"] = translator.revisions
    stats["model_load_seconds"] = translator.load_seconds
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats

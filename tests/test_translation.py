"""Tests of the translation helpers: fakes only, no torch, no model, no psutil."""

from __future__ import annotations

import json
import re
import time

import pytest

from src.data.translation import (
    LowMemoryError,
    MemoryGuard,
    ResourceMonitor,
    Sample,
    append_jsonl,
    has_leftover_code,
    mask_tags,
    read_jsonl,
    select_mixed_sample,
    split_text,
    translate_records,
    translate_texts,
    unmask_tags,
)

MODELS = {"en": {"repo_id": "fake/en-fr"}, "de": {"repo_id": "fake/de-fr"}}


def fake_translate(language: str, segments: list[str]) -> list[str]:
    """Stand-in for the model: upper-case, which also proves the tags are protected."""
    return [s.upper() for s in segments]


# --------------------------------------------------------------------------- segmentation


@pytest.mark.parametrize(
    "text",
    [
        "One sentence.",
        "First sentence. Second sentence!  Third?\nNew line here.\n\nAfter a blank line.",
        "",
        "\n\n",
        "word " * 200,
        "A very long sentence without punctuation " * 30 + "end.",
    ],
)
def test_split_text_gives_back_the_text_when_joined(text):
    assert "".join(seg + sep for seg, sep in split_text(text, max_chars=100)) == text


def test_split_text_respects_the_segment_size():
    pieces = split_text("lorem ipsum " * 100, max_chars=80)
    assert all(len(seg) <= 80 for seg, _ in pieces)
    assert len(pieces) > 1


# --------------------------------------------------------------------------- masking tags


def test_mask_and_unmask_round_trip():
    text = "User [NAME] of [COMPANY] opened [TICKET ID] on [SERVER]."
    masked, table = mask_tags(text)
    assert "[" not in masked
    assert unmask_tags(masked, table) == text


def test_known_tags_get_distinct_codes():
    tags = [
        "NAME", "COMPANY", "LOCATION", "TICKET ID", "SERVER", "USERNAME", "EMAIL", "PHONE",
        "ADDRESS", "IP", "IP_ADDRESS", "MAC_ADDRESS", "PASSWORD", "SOFTWARE", "ID", "URL",
        "SOMETHING NEW",
    ]  # fmt: skip
    masked, table = mask_tags(" ".join(f"[{t}]" for t in tags))
    assert len(table) == len(tags)
    assert len(set(masked.split())) == len(tags)


def test_unmask_tolerates_an_extra_digit_added_by_the_model():
    masked, table = mask_tags("Login [USERNAME]")
    code = next(iter(table))  # ZZ123ZZ
    damaged = masked.replace(code, code[:5] + "9ZZ")
    assert unmask_tags(damaged, table) == "Login [USERNAME]"


def test_has_leftover_code_flags_unrestorable_codes():
    assert has_leftover_code("Nom: ZZ12ZZ")
    assert not has_leftover_code("Nom: [NAME]")


def test_translate_texts_keeps_tags_and_layout():
    result = translate_texts(
        ["Hello [NAME].\nPlease help!", "[EMAIL]", "12345"], "en", fake_translate
    )
    assert result == ["HELLO [NAME].\nPLEASE HELP!", "[EMAIL]", "12345"]


def test_translate_texts_sends_each_distinct_segment_once():
    calls: list[list[str]] = []

    def recorder(language: str, segments: list[str]) -> list[str]:
        calls.append(segments)
        return segments

    translate_texts(["Same line.", "Same line.", "Other line."], "en", recorder)
    assert len(calls) == 1
    assert sorted(calls[0]) == ["Other line.", "Same line."]


# --------------------------------------------------------------------------- memory guard


def test_memory_guard_passes_when_enough_ram():
    MemoryGuard(1500, reader=lambda: 4000).check()


def test_memory_guard_raises_below_threshold():
    guard = MemoryGuard(1500, reader=lambda: 1499.0)
    with pytest.raises(LowMemoryError, match="1499"):
        guard.check("lot 3")


def test_translate_records_stops_cleanly_and_keeps_what_was_saved():
    readings = iter([3000, 3000, 900])  # the third check is under the threshold
    guard = MemoryGuard(1500, reader=lambda: next(readings))
    records = [
        {"id": f"T{i}", "language_source": "en", "subject": f"Subject {i}", "body": f"Body {i}."}
        for i in range(30)
    ]
    saved: list[dict] = []
    stats = translate_records(
        records, fake_translate, guard, saved.extend, MODELS, chunk_size=10, log=lambda _: None
    )
    assert stats["status"] == "stopped_low_memory"
    assert "900" in stats["reason"]
    assert [r["id"] for r in saved] == [f"T{i}" for i in range(20)]  # two chunks saved
    assert saved[0]["subject_fr"] == "SUBJECT 0"
    assert saved[0]["translation_model"] == "fake/en-fr"
    assert saved[0]["translation_flags"] == []
    assert stats["total_tickets"] == 20


def test_translate_records_runs_every_language_and_reports_timings():
    guard = MemoryGuard(1500, reader=lambda: 9000)
    records = [
        {"id": "A", "language_source": "en", "subject": "Hi", "body": "Hello there."},
        {"id": "B", "language_source": "de", "subject": "Hallo", "body": "Guten Tag."},
    ]
    saved: list[dict] = []
    stats = translate_records(
        records, fake_translate, guard, saved.extend, MODELS, log=lambda _: None
    )
    assert stats["status"] == "ok"
    assert set(stats["languages"]) == {"en", "de"}
    assert stats["languages"]["de"]["tickets"] == 1
    assert {r["id"] for r in saved} == {"A", "B"}


def test_translate_records_flags_damaged_tags():
    guard = MemoryGuard(1500, reader=lambda: 9000)
    records = [{"id": "A", "language_source": "en", "subject": "", "body": "Hi [NAME]."}]
    saved: list[dict] = []

    def damaging(language: str, segments: list[str]) -> list[str]:
        """A model that mangles the code into one the table does not know."""
        return [re.sub(r"ZZ\d{3}ZZ", "ZZ12ZZ", s) for s in segments]

    stats = translate_records(records, damaging, guard, saved.extend, MODELS, log=lambda _: None)
    assert saved[0]["translation_flags"] == ["tag_not_restored"]
    assert stats["languages"]["en"]["flagged"] == 1


# --------------------------------------------------------------------------- monitor + sample


def test_resource_monitor_summarises_samples():
    values = iter([Sample(4000, 700, 20, 10), Sample(3500, 900, 40, 30), Sample(3800, 800, 30, 20)])
    monitor = ResourceMonitor(
        interval=0.01, sampler=lambda: next(values, Sample(3800, 800, 30, 20))
    )
    with monitor:
        time.sleep(0.2)
    summary = monitor.summary()
    assert summary["min_available_ram_mb"] == 3500
    assert summary["max_process_rss_mb"] == 900
    assert summary["max_system_cpu_pct"] == 40


def test_resource_monitor_summary_is_empty_without_samples():
    assert ResourceMonitor(interval=10, sampler=lambda: Sample(1, 1, 1, 1)).summary() == {}


def test_select_mixed_sample_spreads_languages_and_is_reproducible():
    records = [{"id": f"E{i}", "language_source": "en"} for i in range(30)]
    records += [{"id": f"D{i}", "language_source": "de"} for i in range(30)]
    records += [{"id": f"P{i}", "language_source": "pt"} for i in range(3)]
    sample = select_mixed_sample(records, 12, seed=7)
    languages = [r["language_source"] for r in sample]
    assert len(sample) == 12
    assert languages.count("pt") == 3  # the small language is fully used
    assert abs(languages.count("en") - languages.count("de")) <= 1
    assert sample == select_mixed_sample(list(reversed(records)), 12, seed=7)


def test_jsonl_helpers_round_trip_accents(tmp_path):
    path = tmp_path / "x" / "out.jsonl"
    append_jsonl(path, [{"a": "é"}])
    append_jsonl(path, [{"a": "ü"}])
    assert read_jsonl(path) == [{"a": "é"}, {"a": "ü"}]
    assert "é" in path.read_text(encoding="utf-8")  # not escaped
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[1]) == {"a": "ü"}

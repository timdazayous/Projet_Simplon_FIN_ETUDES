"""Tests of the translation helpers: fakes only, no torch, no model, no psutil."""

from __future__ import annotations

import json
import re
import time

import pytest

from src.data.translation import (
    Glossary,
    GlossaryTerm,
    LowMemoryError,
    MemoryGuard,
    ResourceMonitor,
    Sample,
    append_jsonl,
    has_leftover_code,
    load_glossary,
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


# --------------------------------------------------------------------------- glossary


def make_glossary() -> Glossary:
    return Glossary(
        [
            GlossaryTerm("Active Directory", ignore_case=True),
            GlossaryTerm("File Share Access", fr="Accès à un partage de fichiers"),
            GlossaryTerm("File Share", fr="Partage de fichiers"),
            GlossaryTerm("Light User", ignore_case=True),
            GlossaryTerm("Teams"),
            GlossaryTerm("VPN"),
        ]
    )


def test_glossary_masks_terms_and_restores_them_as_written_in_the_glossary():
    glossary = make_glossary()
    masked, table = glossary.mask("Create a Light User in Active Directory over the VPN.")
    assert "Light User" not in masked and "Active Directory" not in masked and "VPN" not in masked
    assert unmask_tags(masked, table) == "Create a Light User in Active Directory over the VPN."


def test_glossary_ignore_case_restores_the_canonical_spelling():
    glossary = make_glossary()
    masked, table = glossary.mask("light user and ACTIVE DIRECTORY")
    assert unmask_tags(masked, table) == "Light User and Active Directory"


def test_glossary_respects_case_when_ignore_case_is_off():
    masked, table = make_glossary().mask("Our teams use Teams. vpn and VPN.")
    assert masked.count("ZZ") == 4  # two codes: "Teams" and the upper-case "VPN"
    assert "our teams" in masked.lower() and "vpn and" in masked  # lower-case words untouched


def test_glossary_matches_whole_words_only():
    masked, table = make_glossary().mask("VPNs and MyTeams and Teamsite")
    assert table == {}
    assert masked == "VPNs and MyTeams and Teamsite"


def test_glossary_longest_term_wins_and_fixed_wording_replaces_the_term():
    glossary = make_glossary()
    masked, table = glossary.mask("File Share Access for the File Share")
    assert unmask_tags(masked, table) == (
        "Accès à un partage de fichiers for the Partage de fichiers"
    )
    assert len(table) == 2  # "File Share Access" was not cut into "File Share" + "Access"


def test_glossary_codes_do_not_clash_with_tag_codes():
    glossary = make_glossary()
    masked, table = glossary.mask("Light User [NAME] [COMPANY] [SOMETHING NEW] Active Directory")
    masked, tags = mask_tags(masked)
    assert not set(table) & set(tags)
    assert unmask_tags(masked, {**table, **tags}) == (
        "Light User [NAME] [COMPANY] [SOMETHING NEW] Active Directory"
    )


def test_translate_texts_never_gives_glossary_terms_to_the_model():
    seen: list[str] = []

    def spy(language: str, segments: list[str]) -> list[str]:
        seen.extend(segments)
        return [s.upper() for s in segments]  # the "model" shouts: unprotected terms would change

    result = translate_texts(
        ["Create a Light User in Active Directory for [NAME]"], "en", spy, make_glossary()
    )
    assert result == ["CREATE A Light User IN Active Directory FOR [NAME]"]
    assert all("Light User" not in s and "Active Directory" not in s for s in seen)


def test_translate_texts_without_glossary_is_unchanged():
    assert translate_texts(["Light User"], "en", fake_translate) == ["LIGHT USER"]


def test_translate_records_applies_the_glossary_to_subject_and_body():
    saved: list[dict] = []
    records = [{"id": "1", "language_source": "en", "subject": "Light User", "body": "Use VPN"}]
    translate_records(
        records,
        fake_translate,
        MemoryGuard(1, reader=lambda: 10_000),
        saved.extend,
        MODELS,
        log=lambda _: None,
        glossary=make_glossary(),
    )
    assert saved[0]["subject_fr"] == "Light User"
    assert saved[0]["body_fr"] == "USE VPN"
    assert saved[0]["translation_flags"] == []


def test_load_glossary_reads_a_file_and_refuses_duplicates(tmp_path):
    path = tmp_path / "glossary.yaml"
    path.write_text("terms:\n  - {term: VPN}\n  - {term: Teams, fr: Équipes}\n", encoding="utf-8")
    glossary = load_glossary(path)
    assert [t.term for t in glossary.terms] == ["VPN", "Teams"]
    assert glossary.terms[1].restored == "Équipes"

    path.write_text(
        "terms:\n  - {term: VPN, ignore_case: true}\n  - {term: vpn, ignore_case: true}\n", "utf-8"
    )
    with pytest.raises(ValueError, match="twice"):
        load_glossary(path)


def test_translate_file_resumes_without_retranslating(tmp_path, monkeypatch):
    """The night command restarts where it stopped: tickets already in the output are skipped."""
    import src.data.translation as translation

    class FakeTranslator:
        calls: list[list[str]] = []

        def __init__(self, *args, **kwargs):
            self.revisions = {}
            self.load_seconds = {}

        def translate(self, language, segments):
            FakeTranslator.calls.append(segments)
            return [s.upper() for s in segments]

    monkeypatch.setattr(translation, "OpusTranslator", FakeTranslator)
    monkeypatch.setattr(translation, "MemoryGuard", lambda mb: MemoryGuard(mb, lambda: 10_000))
    # translate_file starts a ResourceMonitor; psutil is not installed in the CI environment.
    monkeypatch.setattr(translation, "_psutil_sampler", lambda: lambda: Sample(4000, 700, 20, 10))
    source, target, report = tmp_path / "in.jsonl", tmp_path / "out.jsonl", tmp_path / "r.json"
    records = [
        {"id": f"T{i}", "language_source": "en", "subject": f"Subject {i}", "body": "Use VPN now"}
        for i in range(3)
    ]
    append_jsonl(source, records)
    append_jsonl(target, [{**records[0], "subject_fr": "DONE"}])  # one ticket already translated

    stats = translation.translate_file(
        source,
        target,
        report,
        MODELS,
        make_glossary(),
        seed=1,
        resume=True,
        log=lambda _: None,
    )
    assert stats["status"] == "ok"
    assert stats["settings"]["already_done"] == 1
    assert [r["id"] for r in read_jsonl(target)] == ["T0", "T1", "T2"]
    assert read_jsonl(target)[0]["subject_fr"] == "DONE"  # not translated again
    assert read_jsonl(target)[1]["body_fr"] == "USE VPN NOW"
    assert json.loads(report.read_text(encoding="utf-8"))["settings"]["beams"] == 2

    translation.translate_file(
        source, target, report, MODELS, None, seed=1, resume=False, log=lambda _: None
    )
    assert len(read_jsonl(target)) == 3  # a fresh run replaces the output
    assert read_jsonl(target)[0]["subject_fr"] == "SUBJECT 0"


def test_glossary_is_limited_to_the_code_range():
    with pytest.raises(ValueError, match="at most"):
        Glossary([GlossaryTerm(f"term{i}") for i in range(101)])


def test_real_glossary_is_valid_and_covers_the_terms_found_mistranslated():
    glossary = load_glossary()
    terms = {t.term for t in glossary.terms}
    assert {"Active Directory", "Light User", "Basis User", "VPN", "Outlook", "Teams"} <= terms
    assert {"SharePoint", "OneDrive", "Exchange", "Citrix"} <= terms
    assert {"Office 365", "O365"} <= terms
    masked, table = glossary.mask("Remove File Share Access for the Light User in Office 365")
    assert unmask_tags(masked, table) == (
        "Suppression d'accès à un partage de fichiers for the Light User in Office 365"
    )

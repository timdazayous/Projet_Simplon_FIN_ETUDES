"""Tests of the public-dataset pipeline: no download, no model, no pyarrow."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.data.label_mapping import LabelMapping
from src.data.public_datasets import (
    DatasetSpec,
    LicenseError,
    PublicConfig,
    check_license,
    dedup_key,
    detect_language,
    filter_records,
    is_corrupted,
    load_config,
    normalise_text,
    prepare_dataset,
    run_fetch,
    sample_records,
    to_record,
)

TAGS = [f"tag_{i}" for i in range(1, 9)]


def make_spec(**overrides) -> DatasetSpec:
    values = {
        "name": "customer_support",
        "repo_id": "owner/dataset",
        "expected_license": "cc-by-nc-4.0",
        "role": "train",
        "id_prefix": "PUB-X",
        "format": "tobi_csv",
        "files": ("data.csv",),
        "languages": ("en", "de"),
        "language_source": "column",
        "min_chars": 20,
        "max_chars": 500,
        "attribution": "Someone",
        "max_records": None,
        "queues": ("IT Support",),
    }
    values.update(overrides)
    return DatasetSpec(**values)


def row(subject, body, queue="IT Support", language="en", index=1, **extra):
    base = {
        "subject": subject,
        "body": body,
        "queue": queue,
        "language": language,
        "type": "Incident",
        "priority": "high",
        "_row": index,
        "_file": "data.csv",
    }
    base.update({tag: None for tag in TAGS})
    base.update(extra)
    return base


EN_BODY = "The printer on the second floor does not work and we need it for the invoices."


# --------------------------------------------------------------------------- normalisation


def test_normalise_text_converts_literal_newlines_and_spaces():
    assert (
        normalise_text("Hello,\\n\\nthe printer   is\r\ndown  ") == "Hello,\n\nthe printer is\ndown"
    )


def test_normalise_text_handles_empty_values():
    assert normalise_text(None) == ""
    assert normalise_text("   ") == ""


def test_normalise_text_removes_control_characters():
    assert normalise_text("ab\x00c\x07d") == "abcd"


def test_is_corrupted_detects_replacement_characters_and_mojibake():
    assert is_corrupted("M����ngel im Prozess")
    assert is_corrupted("TÃ©lÃ©phone cassÃ©")
    assert not is_corrupted("Un texte parfaitement lisible, avec des accents : é à ü.")
    assert not is_corrupted("")


def test_dedup_key_ignores_case_and_spacing():
    assert dedup_key("Hello", "World  x") == dedup_key("hello", " world x")


# --------------------------------------------------------------------------- language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Please reset the password of my account, thanks", "en"),
        ("Bitte setzen Sie das Passwort zurück, ich kann nicht auf den Server zugreifen", "de"),
        ("No puedo ingresar al correo, necesito ayuda con el problema", "es"),
        ("Preciso de acesso à pasta do servidor, não consigo entrar", "pt"),
        ("[NAME] [COMPANY]", None),
        ("", None),
    ],
)
def test_detect_language(text, expected):
    assert detect_language(text) == expected


# --------------------------------------------------------------------------- licence


def test_check_license_accepts_expected_licence_whatever_the_case():
    check_license(make_spec(), "CC-BY-NC-4.0")


@pytest.mark.parametrize("actual", ["mit", "cc-by-4.0", None, ""])
def test_check_license_refuses_other_licences(actual):
    with pytest.raises(LicenseError, match="Refusing to download"):
        check_license(make_spec(), actual)


# --------------------------------------------------------------------------- filtering


def test_filter_records_counts_every_rejection_reason_once():
    spec = make_spec()
    rows = [
        row("Printer", EN_BODY, index=1),  # kept
        row("Printer", EN_BODY.upper(), index=2),  # duplicate (case ignored)
        row("Billing", EN_BODY, queue="Billing", index=3),  # not an IT queue
        row("Empty", "", index=4),  # empty body
        row("Short", "ok", index=5),  # too short
        row("Long", "word " * 200, index=6),  # too long
        row("Broken", "T����l�phone " * 3, index=7),  # corrupted
        row("Autre", "La imprimante no funciona y necesito ayuda urgente", language="fr", index=8),
    ]
    kept, rejected, notes = filter_records(spec, rows)
    assert [r["origin_id"] for r in kept] == ["data.csv:1"]
    assert dict(rejected) == {
        "duplicate": 1,
        "queue": 1,
        "empty": 1,
        "too_short": 1,
        "too_long": 1,
        "corrupted": 1,
        "language": 1,
    }
    assert not notes


def test_filter_records_corrects_a_wrong_declared_language():
    spec = make_spec()
    rows = [
        row(
            "Drucker",
            "Der Drucker im zweiten Stock funktioniert nicht, bitte helfen Sie",
            language="en",
        )
    ]
    kept, _, notes = filter_records(spec, rows)
    assert kept[0]["language_source"] == "de"
    assert notes["language_corrected"] == 1


def test_filter_records_keeps_original_labels_and_tags():
    spec = make_spec()
    kept, _, _ = filter_records(spec, [row("Printer", EN_BODY, tag_1="Hardware", tag_2=" Bug ")])
    assert kept[0]["original_labels"] == {
        "queue": "IT Support",
        "type": "Incident",
        "priority": "high",
        "tags": ["Hardware", "Bug"],
    }


def test_filter_records_detects_language_for_datasets_without_column():
    spec = make_spec(
        format="tasksource_parquet",
        language_source="detect",
        queues=(),
        label_names=("Active Directory", "Software"),
        languages=("en", "pt"),
        strip_prefixes=(r"^\[TICKET ID\]\s*-\s*New Support Ticket received\s*-\s*",),
        min_chars=5,
    )
    rows = [
        {
            "text": (
                "[TICKET ID] - New Support Ticket received - "
                "Cannot reset the password of my account"
            ),
            "label": 1,
            "_row": 1,
            "_split": "test",
        },
        {
            "text": "Preciso de acesso à pasta do servidor, não consigo entrar",
            "label": 0,
            "_row": 2,
            "_split": "test",
        },
        {"text": "text with a bad label", "label": 9, "_row": 3, "_split": "test"},
    ]
    kept, rejected, _ = filter_records(spec, rows)
    assert [r["language_source"] for r in kept] == ["en", "pt"]
    assert kept[0]["body"] == "Cannot reset the password of my account"  # prefix removed
    assert kept[0]["original_labels"] == {"label": "Software"}
    assert rejected["unreadable"] == 1


def test_to_record_urgency_keeps_label_and_case_id():
    spec = make_spec(format="urgency_jsonl", queues=())
    record = to_record(
        spec,
        {
            "case_id": "urgency-0001",
            "state": "Everything is down",
            "expected": "urgent",
            "category": "request",
            "language": "en",
            "split": "test",
            "_row": 1,
        },
    )
    assert record["origin_id"] == "urgency-0001"
    assert record["original_labels"]["expected"] == "urgent"


# --------------------------------------------------------------------------- sampling


def test_sample_records_is_reproducible_and_respects_the_limit():
    records = [{"origin_id": f"f:{i:03d}"} for i in range(100)]
    first = sample_records(records, 10, seed=42)
    assert first == sample_records(list(reversed(records)), 10, seed=42)
    assert len(first) == 10
    assert first != sample_records(records, 10, seed=43)
    assert sample_records(records, None, seed=1) == sorted(records, key=lambda r: r["origin_id"])


# --------------------------------------------------------------------------- orchestration


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = [
        "subject",
        "body",
        "answer",
        "type",
        "queue",
        "priority",
        "language",
        "version",
        *TAGS,
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in columns})


class FakeHub:
    def __init__(self, licence: str | None, source: Path, fail_download: bool = False):
        self.licence = licence
        self.source = source
        self.fail_download = fail_download
        self.downloads: list[str] = []

    def get_license(self, repo_id: str) -> str | None:
        return self.licence

    def download(self, repo_id: str, filename: str, cache_dir: Path) -> Path:
        self.downloads.append(filename)
        if self.fail_download:
            raise OSError("network down")
        return self.source


def make_config(tmp_path: Path, spec: DatasetSpec) -> PublicConfig:
    return PublicConfig(
        seed=1,
        output_directory=tmp_path / "out",
        cache_directory=tmp_path / "cache",
        datasets={spec.name: spec},
    )


def test_run_fetch_writes_jsonl_and_report(tmp_path):
    spec = make_spec()
    source = tmp_path / "data.csv"
    write_csv(
        source,
        [
            {
                "subject": "Printer",
                "body": EN_BODY,
                "queue": "IT Support",
                "language": "en",
                "type": "Incident",
                "priority": "low",
                "tag_1": "Printer",
            },
            {
                "subject": "Billing",
                "body": EN_BODY + " again",
                "queue": "Billing",
                "language": "en",
            },
        ],
    )
    config = make_config(tmp_path, spec)
    mapping = LabelMapping(
        rules={
            "customer_support": {
                "type": {"Incident": "incident"},
                "priority": {"low": "P4"},
                "category_rules": [
                    {"name": "printing", "category": "printing", "tags": ["Printer"]}
                ],
            }
        }
    )
    reports = run_fetch(config, mapping, FakeHub("cc-by-nc-4.0", source), log=lambda _: None)

    assert reports["customer_support"]["saved"] == 1
    lines = (
        (config.output_directory / "customer_support_prepared.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    record = json.loads(lines[0])
    assert record["id"] == "PUB-X-00001"
    assert record["origin_id"] == "data.csv:1"
    assert record["proposed_labels"]["category"] == "printing"
    assert record["proposed_labels"]["priority"] == "P4"
    assert record["original_labels"]["queue"] == "IT Support"
    assert record["license"] == "cc-by-nc-4.0"
    assert (config.output_directory / "prepare_report.json").exists()


def test_run_fetch_refuses_before_any_download_when_licence_differs(tmp_path):
    spec = make_spec()
    hub = FakeHub("mit", tmp_path / "data.csv")
    with pytest.raises(LicenseError):
        run_fetch(make_config(tmp_path, spec), LabelMapping(), hub, log=lambda _: None)
    assert hub.downloads == []
    assert not (tmp_path / "out" / "customer_support_prepared.jsonl").exists()


def test_run_fetch_reports_a_download_failure_without_crashing(tmp_path):
    spec = make_spec()
    hub = FakeHub("cc-by-nc-4.0", tmp_path / "data.csv", fail_download=True)
    reports = run_fetch(make_config(tmp_path, spec), LabelMapping(), hub, log=lambda _: None)
    assert "network down" in reports["customer_support"]["error"]


def test_prepare_dataset_limit_overrides_max_records(tmp_path):
    spec = make_spec(max_records=5)
    source = tmp_path / "data.csv"
    write_csv(
        source,
        [
            {
                "subject": f"Ticket {i}",
                "body": f"{EN_BODY} number {i}",
                "queue": "IT Support",
                "language": "en",
            }
            for i in range(8)
        ],
    )
    records, report = prepare_dataset(spec, [source], LabelMapping(), seed=1, limit=3)
    assert len(records) == 3
    assert report["rows_read"] == 8


def test_real_configuration_is_consistent():
    config = load_config()
    assert set(config.datasets) == {"customer_support", "it_support", "support_urgency"}
    for spec in config.datasets.values():
        assert spec.expected_license in {"cc-by-nc-4.0", "cc-by-4.0"}
        assert set(spec.languages) <= set(config.translation_models)
    assert all(m["license"] == "apache-2.0" for m in config.translation_models.values())

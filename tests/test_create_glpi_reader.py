"""Tests of the helper that creates the read-only MariaDB account (Issue #53). No Docker."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_glpi_reader.py"
spec = importlib.util.spec_from_file_location("create_glpi_reader", SCRIPT)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

PASSWORD = "a-long-enough-password-1"


def test_sql_input_sets_session_variables_before_the_versioned_script() -> None:
    result = reader.build_sql_input("glpi_reader", PASSWORD, "glpi", "-- fichier\nSELECT 1;\n")
    assert result.startswith("SET @reader_user = 'glpi_reader';")
    assert f"SET @reader_password = '{PASSWORD}';" in result
    assert result.endswith("SELECT 1;\n")


def test_quotes_and_backslashes_in_the_password_are_escaped() -> None:
    assert reader.sql_literal("it's\\ok") == "'it''s\\\\ok'"


@pytest.mark.parametrize(
    ("user", "password", "database"),
    [
        ("a'; DROP USER x; --", PASSWORD, "glpi"),
        ("reader", PASSWORD, "g`lpi"),
        ("reader", "court", "glpi"),
    ],
)
def test_invalid_values_are_refused(user: str, password: str, database: str) -> None:
    with pytest.raises(ValueError):
        reader.build_sql_input(user, password, database, "")


def test_password_goes_through_stdin_only(tmp_path: Path, monkeypatch, capsys) -> None:
    env = tmp_path / ".env"
    env.write_text(
        f"GLPI_DB_READER_USER=glpi_reader\nGLPI_DB_READER_PASSWORD={PASSWORD}\n", "utf-8"
    )
    calls: list[tuple[list[str], str]] = []

    def fake_run(command, input, **kwargs):
        calls.append((command, input))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="GRANT SELECT ON x\nGRANT USAGE IDENTIFIED BY PASSWORD '*HASH'\n",
            stderr="",
        )

    monkeypatch.setattr(reader.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["create_glpi_reader.py", "--env-file", str(env)])
    assert reader.main() == 0
    command, stdin = calls[0]
    assert PASSWORD not in " ".join(command)
    assert PASSWORD in stdin
    output = capsys.readouterr().out
    assert PASSWORD not in output and "*HASH" not in output
    assert "GRANT SELECT ON x" in output


def test_missing_variables(tmp_path: Path, monkeypatch, capsys) -> None:
    env = tmp_path / ".env"
    env.write_text("GLPI_DB_NAME=glpi\n", "utf-8")
    monkeypatch.setattr(sys, "argv", ["create_glpi_reader.py", "--env-file", str(env)])
    assert reader.main() == 2

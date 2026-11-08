"""Tests of the SQL extraction of GLPI tickets (Issue #53). No database: fake connection."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pymysql
import pytest

from src.data import glpi_sql
from src.data.glpi_sql import SqlConfig, run_extraction
from src.data.pseudonymize import Pseudonymizer

KEY = "k" * 40
RAW_EMAIL = "camille.vaudrelle@fournilune.test"
RAW_PHONE = "01 99 00 12 34"
RAW_SECRET = "Zx9-hunter2"
RAW_NAME = "Camille Vaudrelle"


def ticket_row(ticket_id: int = 101, **overrides: Any) -> dict[str, Any]:
    row = {
        "id": ticket_id,
        "date": datetime(2026, 3, 1, 9, 0, 0),
        "date_mod": datetime(2026, 3, 1, 9, 0, 0),
        "name": f"Plus d'Internet chez {RAW_NAME}",
        "content": (
            "&lt;p&gt;Bonjour,&lt;/p&gt;&lt;p&gt;Mon mot de passe actuel est "
            f"{RAW_SECRET}, rappelez Camille au {RAW_PHONE} ou {RAW_EMAIL}.&lt;br&gt;"
            "Merci d&#039;avance&lt;/p&gt;"
        ),
        "status": 1,
        "type": 1,
        "priority": 4,
        "externalid": f"GEN-T-{ticket_id:06d}",
        "category_code": "network",
        "entity_name": "Cabinet Fournilune",
        "followup_count": 2,
    }
    return row | overrides


REQUESTER = {
    "tickets_id": 101,
    "users_id": 21,
    "alternative_email": None,
    "firstname": "Camille",
    "realname": "Vaudrelle",
}


class FakeCursor:
    def __init__(self, db: FakeConnection) -> None:
        self.db = db
        self._rows: list[dict[str, Any]] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        self.db.queries.append((sql, params))
        if self.db.fail_with:
            raise self.db.fail_with
        if "glpi_tickets_users" in sql:
            self._rows = [r for r in self.db.requesters if r["tickets_id"] in params]
        elif sql.startswith("EXPLAIN"):
            self._rows = [{"id": 1, "table": "t", "key": "date_mod"}]
        else:
            self._rows = self.db.tickets[: params["limit"]]

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class FakeConnection:
    def __init__(self, tickets=None, requesters=None) -> None:
        self.tickets = tickets if tickets is not None else [ticket_row()]
        self.requesters = requesters if requesters is not None else [REQUESTER]
        self.queries: list[tuple[str, Any]] = []
        self.fail_with: Exception | None = None
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def config() -> SqlConfig:
    return SqlConfig("127.0.0.1", 3307, "glpi", "reader", "reader-password-value", backoff=1.0)


@pytest.fixture
def pseudo() -> Pseudonymizer:
    return Pseudonymizer(KEY)


def extract(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path, db: FakeConnection, **kw: Any
):
    sleeps: list[float] = []
    kw.setdefault("connection_factory", lambda _config: db)
    report = run_extraction(config, pseudo, output_directory=tmp_path, sleep=sleeps.append, **kw)
    return report, sleeps


def read_output(tmp_path: Path) -> list[dict[str, Any]]:
    lines = (tmp_path / "tickets.jsonl").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines]


# --------------------------------------------------------------------------- queries


def test_queries_are_parameterised_and_exclude_deleted_tickets() -> None:
    query = glpi_sql.load_query("tickets.sql")
    assert "%(since)s" in query and "%(limit)s" in query
    assert "t.is_deleted = 0" in query
    assert "t.date_mod >= %(since)s" in query
    assert "SELECT *" not in query.upper().replace("SELECT\n", "")
    assert "--" not in query  # comments dropped: a "%" in a comment would break the binding
    requesters = glpi_sql.load_query("requesters.sql")
    assert "{ids}" in requesters and "tu.type = 1" in requesters


def test_reader_script_grants_select_only_and_holds_no_secret() -> None:
    text = (glpi_sql.SQL_DIRECTORY / "create_reader.sql").read_text("utf-8")
    sql = "\n".join(line for line in text.splitlines() if not line.startswith("--"))
    statements = [line for line in sql.splitlines() if "'GRANT " in line]
    assert statements
    assert all("SELECT" in line for line in statements)
    for forbidden in ("ALL PRIVILEGES", "INSERT", "UPDATE", "DELETE", "GRANT OPTION", "glpi`.*"):
        assert forbidden not in sql.replace("GRANT SELECT (", "")
    assert not re.search(r"IDENTIFIED BY '\w", sql)  # the password is a session variable


# --------------------------------------------------------------------------- conversion


def test_html_to_text() -> None:
    assert glpi_sql.html_to_text(
        "&lt;p&gt;Bonjour&lt;/p&gt;&lt;p&gt;a&lt;br&gt;b &amp;amp; c&lt;/p&gt;"
    ) == ("Bonjour\n\na\nb & c")
    assert glpi_sql.html_to_text("<p>Déjà <b>propre</b></p>") == "Déjà propre"
    assert glpi_sql.html_to_text("l&#039;été") == "l'été"
    assert glpi_sql.html_to_text(None) == ""


def test_record_follows_the_common_schema(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    report, _ = extract(config, pseudo, tmp_path, FakeConnection(), full=True)
    assert report.exit_code() == glpi_sql.EXIT_OK
    record = read_output(tmp_path)[0]
    assert record["id"] == "GLPI-101" and record["origin_id"] == "101"
    assert record["source"] == "glpi" and record["label_origin"] == "glpi_input"
    assert record["created_at"] == "2026-03-01T09:00:00+00:00"  # UTC, ISO 8601
    assert (record["category"], record["type"], record["priority"]) == ("network", "incident", "P2")
    assert record["team"] is None and record["channel"] is None
    assert record["external_ref"] == "GEN-T-000101"
    assert record["followup_count"] == 2
    assert record["client"] == "Cabinet Fournilune"
    assert record["requesters"] == [pseudo.pseudonym(21)]


def test_no_raw_personal_data_reaches_the_disk_or_the_logs(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    report, _ = extract(config, pseudo, tmp_path, FakeConnection(), full=True)
    on_disk = "".join(p.read_text("utf-8") for p in tmp_path.iterdir())
    for raw in (RAW_EMAIL, RAW_PHONE, RAW_SECRET, "Vaudrelle", "Camille"):
        assert raw not in on_disk
        assert raw not in caplog.text
    assert report.masked["email"] == 1 and report.masked["phone"] == 1
    assert report.masked["secret"] == 1 and report.masked["name"] >= 2
    assert "Merci d'avance" in on_disk  # the rest of the text is kept


def test_unknown_or_missing_category_is_left_empty_and_counted(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    db = FakeConnection(
        [
            ticket_row(1, category_code="inconnue_xyz"),
            ticket_row(2, category_code=None),
            ticket_row(3, type=2, priority=2),
        ],
        [],
    )
    report, _ = extract(config, pseudo, tmp_path, db, full=True)
    records = read_output(tmp_path)
    assert [r["category"] for r in records] == [None, None, "network"]
    assert (report.unknown_category, report.no_category) == (1, 1)
    assert (records[2]["type"], records[2]["priority"]) == ("service_request", "P4")


def test_ticket_without_any_text_is_skipped_and_counted(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    db = FakeConnection([ticket_row(1, name="", content=None), ticket_row(2)], [])
    report, _ = extract(config, pseudo, tmp_path, db, full=True)
    assert (report.rows_read, report.records_written, report.skipped_empty_text) == (2, 1, 1)


def test_requester_without_account_is_pseudonymised_from_the_alternative_email(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    requester = {
        "tickets_id": 101,
        "users_id": 0,
        "alternative_email": "anonyme@fournilune.test",
        "firstname": None,
        "realname": None,
    }
    extract(config, pseudo, tmp_path, FakeConnection(requesters=[requester]), full=True)
    assert read_output(tmp_path)[0]["requesters"] == [pseudo.pseudonym("anonyme@fournilune.test")]


# --------------------------------------------------------------------------- incremental


def test_incremental_run_starts_from_the_saved_state_and_binds_the_date(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    first = FakeConnection(
        [ticket_row(1), ticket_row(2, date_mod=datetime(2026, 3, 5, 8, 0, 0))], []
    )
    extract(config, pseudo, tmp_path, first)
    assert json.loads((tmp_path / "state.json").read_text("utf-8")) == {
        "last_date_mod": "2026-03-05T08:00:00+00:00"
    }
    second = FakeConnection(
        [ticket_row(2, date_mod=datetime(2026, 3, 5, 8, 0, 0), name="Modifié")], []
    )
    report, _ = extract(config, pseudo, tmp_path, second)
    sql, params = second.queries[0]
    assert params["since"] == datetime(2026, 3, 5, 8, 0, 0)  # bound parameter, naive UTC
    assert "2026" not in sql  # never concatenated into the query
    assert report.since == "2026-03-05T08:00:00+00:00"
    records = read_output(tmp_path)
    assert [r["origin_id"] for r in records] == ["1", "2"]  # upsert: no duplicate
    assert records[1]["subject"] == "Modifié"
    assert report.records_total == 2


def test_full_option_ignores_the_state_and_rebuilds_the_file(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    extract(config, pseudo, tmp_path, FakeConnection([ticket_row(1), ticket_row(2)], []))
    db = FakeConnection([ticket_row(3)], [])
    report, _ = extract(config, pseudo, tmp_path, db, full=True)
    assert db.queries[0][1]["since"].year == 1970
    assert [r["origin_id"] for r in read_output(tmp_path)] == ["3"]
    assert report.records_total == 1


def test_explicit_since_and_limit(config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path) -> None:
    db = FakeConnection([ticket_row(i) for i in range(1, 6)], [])
    since = datetime(2026, 1, 1, tzinfo=UTC)
    report, _ = extract(config, pseudo, tmp_path, db, since=since, limit=2)
    assert db.queries[0][1] == {"since": datetime(2026, 1, 1), "limit": 2}
    assert report.records_written == 2


def test_nothing_new_keeps_the_state_and_the_file(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    extract(config, pseudo, tmp_path, FakeConnection())
    before = (tmp_path / "state.json").read_text("utf-8")
    report, _ = extract(config, pseudo, tmp_path, FakeConnection([], []))
    assert report.rows_read == 0
    assert (tmp_path / "state.json").read_text("utf-8") == before
    assert len(read_output(tmp_path)) == 1


def test_corrupted_state_falls_back_to_a_full_extraction(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    (tmp_path / "state.json").write_text("{pas du json", "utf-8")
    db = FakeConnection()
    extract(config, pseudo, tmp_path, db)
    assert db.queries[0][1]["since"].year == 1970


def test_requesters_are_read_in_batches_with_placeholders_only(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    db = FakeConnection([ticket_row(i) for i in range(1, 1202)], [])
    extract(config, pseudo, tmp_path, db, full=True)
    requester_queries = [q for q in db.queries if "glpi_tickets_users" in q[0]]
    assert len(requester_queries) == 3  # 500 + 500 + 201
    sql, params = requester_queries[0]
    assert sql.count("%s") == len(params) == 500
    assert "101" not in sql


# --------------------------------------------------------------------------- errors


def test_connection_errors_are_retried_with_growing_waits_then_reported(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    def refuse(_config: SqlConfig) -> Any:
        raise pymysql.err.OperationalError(2003, "Can't connect")

    report, sleeps = extract(config, pseudo, tmp_path, FakeConnection(), connection_factory=refuse)
    assert report.unavailable and report.exit_code() == glpi_sql.EXIT_UNAVAILABLE
    assert sleeps == [1.0, 2.0, 4.0]
    assert not (tmp_path / "tickets.jsonl").exists()


def test_access_denied_is_not_retried(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    def deny(_config: SqlConfig) -> Any:
        raise pymysql.err.OperationalError(1045, "Access denied for user")

    report, sleeps = extract(config, pseudo, tmp_path, FakeConnection(), connection_factory=deny)
    assert report.exit_code() == glpi_sql.EXIT_AUTH
    assert sleeps == []


def test_a_failing_query_is_reported_and_the_connection_closed(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    db = FakeConnection()
    db.fail_with = pymysql.err.ProgrammingError(1142, "SELECT command denied")
    report, _ = extract(config, pseudo, tmp_path, db, full=True)
    assert report.exit_code() == glpi_sql.EXIT_QUERY
    assert db.closed
    assert not (tmp_path / "state.json").exists()  # no progress saved on failure


def test_the_connection_is_closed_after_a_normal_run(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    db = FakeConnection()
    extract(config, pseudo, tmp_path, db)
    assert db.closed


def test_explain_writes_the_plan_and_reads_no_ticket(
    config: SqlConfig, pseudo: Pseudonymizer, tmp_path: Path
) -> None:
    db = FakeConnection()
    extract(config, pseudo, tmp_path, db, explain=True)
    assert db.queries[0][0].startswith("EXPLAIN")
    assert "key=date_mod" in (tmp_path / "explain.txt").read_text("utf-8")
    assert not (tmp_path / "tickets.jsonl").exists()


# --------------------------------------------------------------------------- configuration


def write_env(tmp_path: Path, **overrides: str) -> Path:
    values = {
        "GLPI_DB_READER_USER": "reader",
        "GLPI_DB_READER_PASSWORD": "pw-secret-value",
        "GLPI_DB_HOST_PORT": "3307",
        "GLPI_DB_NAME": "glpi",
    } | overrides
    path = tmp_path / ".env"
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()), "utf-8")
    return path


def test_load_config(tmp_path: Path) -> None:
    config = glpi_sql.load_sql_config(write_env(tmp_path))
    assert (config.host, config.port, config.database, config.user) == (
        "127.0.0.1",
        3307,
        "glpi",
        "reader",
    )
    assert "pw-secret-value" not in repr(config)


def test_load_config_names_missing_variables_without_values(tmp_path: Path) -> None:
    with pytest.raises(glpi_sql.SqlConfigError) as error:
        glpi_sql.load_sql_config(write_env(tmp_path, GLPI_DB_READER_PASSWORD=""))
    assert "GLPI_DB_READER_PASSWORD" in str(error.value)
    with pytest.raises(glpi_sql.SqlConfigError):
        glpi_sql.load_sql_config(tmp_path / "absent.env")
    with pytest.raises(glpi_sql.SqlConfigError):
        glpi_sql.load_sql_config(write_env(tmp_path, GLPI_DB_HOST_PORT="abc"))

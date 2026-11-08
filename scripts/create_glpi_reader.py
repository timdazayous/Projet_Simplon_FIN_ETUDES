"""Create (or refresh) the read-only MariaDB account used by the GLPI extraction (Issue #53).

Run once by the developer, with the administrator rights of the GLPI database container:

    uv run python scripts/create_glpi_reader.py

It reads GLPI_DB_READER_USER, GLPI_DB_READER_PASSWORD and GLPI_DB_NAME from the env file and
feeds ``sql/glpi/create_reader.sql`` to ``mariadb`` inside the ``glpi-db`` container. The
password travels through the standard input only: it is never on a command line (visible in the
process list) and never printed. The administrator password is read by the container itself from
its own environment (MARIADB_ROOT_PASSWORD): this script never sees it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "glpi" / "create_reader.sql"
IDENTIFIER = re.compile(r"[A-Za-z0-9_]{1,32}")
# The administrator password stays inside the container (MYSQL_PWD is not in the process list).
CONTAINER_COMMAND = 'MYSQL_PWD="$MARIADB_ROOT_PASSWORD" mariadb -uroot'


def sql_literal(value: str) -> str:
    """Quote a value as a SQL string literal (backslash and quote escaped)."""
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def build_sql_input(user: str, password: str, database: str, sql_text: str) -> str:
    """The variable assignments followed by the versioned SQL file."""
    if not IDENTIFIER.fullmatch(user) or not IDENTIFIER.fullmatch(database):
        raise ValueError("nom d'utilisateur ou de base invalide (lettres, chiffres, _ ; 32 max)")
    if len(password) < 16:
        raise ValueError("mot de passe trop court (16 caractères minimum)")
    header = (
        f"SET @reader_user = {sql_literal(user)};\n"
        f"SET @reader_password = {sql_literal(password)};\n"
        f"SET @reader_db = {sql_literal(database)};\n"
    )
    return header + sql_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--container", default="glpi-db")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    user, password = values.get("GLPI_DB_READER_USER"), values.get("GLPI_DB_READER_PASSWORD")
    if not user or not password:
        print("GLPI_DB_READER_USER et GLPI_DB_READER_PASSWORD doivent être renseignés dans .env")
        return 2
    try:
        sql_input = build_sql_input(
            user, password, values.get("GLPI_DB_NAME") or "glpi", SQL_FILE.read_text("utf-8")
        )
    except ValueError as error:
        print(f"Valeur invalide : {error}")
        return 2
    result = subprocess.run(
        ["docker", "exec", "-i", args.container, "sh", "-c", f"{CONTAINER_COMMAND} --table"],
        input=sql_input,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    # Only the SELECT grants are shown: the USAGE line carries the password hash, and an error
    # message could quote the statement (so nothing is printed on failure).
    if result.returncode == 0:
        sys.stdout.reconfigure(encoding="utf-8")
        print("\n".join(line for line in result.stdout.splitlines() if "GRANT SELECT" in line))
        print(f"Compte {user} prêt (SELECT uniquement).")
    else:
        print("Échec de la création du compte (voir docs/glpi.md, section dépannage).")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

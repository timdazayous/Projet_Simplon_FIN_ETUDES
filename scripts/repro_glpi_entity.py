"""Reproduce Issue #58: create one GLPI entity through API v2 and check that its name is stored.

Usage:
    uv run python scripts/repro_glpi_entity.py --name REPRO-TEST

The entity is created under the root entity with the API user of ``.env``, then read back twice:
in the same session, then in a new one (GLPI caches the visible entities per session, see
glpi-project/glpi#14971). Only status codes, the identifier, the name and the level are printed:
never a token or a password.

Exit codes: 0 name stored (profile has the entity UPDATE right), 1 name lost (bug #58 reproduced),
2 configuration error, 4 GLPI unreachable. The test entity stays in GLPI: delete it as Super-Admin.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.glpi_api import (  # noqa: E402
    GlpiClient,
    GlpiConfigError,
    GlpiUnavailable,
    load_api_config,
)

ROOT_ENTITY_ID = 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="name of the test entity")
    parser.add_argument("--env-file", default=".env", help="file holding the secrets")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        config = load_api_config(args.env_file)
    except GlpiConfigError as error:
        print(f"Configuration invalide : {error}")
        return 2
    payload = {"name": args.name, "parent": {"id": ROOT_ENTITY_ID}}
    try:
        with GlpiClient(config) as client:
            response = client.request("POST", "/Administration/Entity", json=payload)
            entity_id = int(response.json()["id"])
            print(f"POST /Administration/Entity : {response.status_code}, id {entity_id}")
            same = client.request("GET", f"/Administration/Entity/{entity_id}").json()
            print(f"Même session     : nom {same.get('name')!r}, niveau {same.get('level')}")
        with GlpiClient(config) as fresh:
            other = fresh.request("GET", f"/Administration/Entity/{entity_id}").json()
            print(f"Nouvelle session : nom {other.get('name')!r}, niveau {other.get('level')}")
    except GlpiUnavailable as error:
        print(f"GLPI indisponible : {error}")
        return 4
    if other.get("name") == args.name:
        print("Nom enregistré : le profil a le droit Modifier sur les entités.")
        return 0
    print("Nom perdu : bug #58 reproduit (droit Modifier sur les entités absent du profil).")
    return 1


if __name__ == "__main__":
    sys.exit(main())

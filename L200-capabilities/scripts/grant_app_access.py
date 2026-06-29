"""Grant a deployed app's service principal the Unity Catalog access it needs.

A Databricks App runs as its own service principal (SP). For the agent to call its
UC-function tools and read its data, that SP needs UC grants — without them the app
boots but every tool call fails with a permission error. This script issues the grants:

    USE CATALOG          on the catalog
    USE SCHEMA           on each schema (tools + data)
    EXECUTE              on every function in the tools schema (the agent's tools)
    SELECT               on every table in the data schema(s) (what the functions read)

Nothing is hardcoded. The SP and catalog are PARAMETERS; the schemas and warehouse come
from flags or the environment, so the same script runs in any workshop attendee's
workspace.

Usage
-----
    # Get the app's SP client id from the deployed app:
    databricks apps get <app-name> --output json | jq -r '.service_principal_client_id'

    uv run python scripts/grant_app_access.py \
        --service-principal <sp-client-id> \
        --catalog $AKZO_CATALOG \
        --tools-schema akzo_tools \
        --data-schema akzo_finance

`--catalog` defaults to AKZO_CATALOG, `--tools-schema` to AKZO_TOOLS_SCHEMA (or
"akzo_tools"). Pass `--data-schema` once per schema the tools read from. The SQL
warehouse is discovered automatically unless DATABRICKS_WAREHOUSE_ID is set.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

from action_plane import databricks_client as dbx  # noqa: E402 — after load_dotenv

_IDENT = re.compile(r"[A-Za-z0-9_]+")


def _validate_ident(kind: str, value: str) -> str:
    """Reject anything that is not a bare SQL identifier (no injection into GRANT)."""
    if not value or not _IDENT.fullmatch(value):
        print(f"Error: unsafe {kind}: {value!r} (expected a bare identifier).", file=sys.stderr)
        sys.exit(1)
    return value


def _grant(sql: str) -> None:
    print(f"  {sql}")
    dbx.run_sql(sql)


def grant_app_access(sp: str, catalog: str, tools_schema: str, data_schemas: list[str]) -> None:
    # The principal is quoted with backticks so a client-id UUID is a valid identifier.
    principal = f"`{sp}`"

    print(f"Granting UC access to service principal {sp} ...")
    _grant(f"GRANT USE CATALOG ON CATALOG {catalog} TO {principal}")

    schemas = list(dict.fromkeys([tools_schema, *data_schemas]))
    for schema in schemas:
        _grant(f"GRANT USE SCHEMA ON SCHEMA {catalog}.{schema} TO {principal}")

    # EXECUTE on every function in the tools schema — these are the agent's tools.
    _grant(
        f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {catalog}.{tools_schema} TO {principal}"
    )

    # SELECT on every table in each data schema — what the functions read.
    for schema in data_schemas:
        _grant(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA {catalog}.{schema} TO {principal}"
        )

    print(
        "\nGrants complete. If a function or table did not exist yet, register it and "
        "re-run this script. Tip: ALL FUNCTIONS / ALL TABLES does not cover objects "
        "created afterwards — re-run after adding new tools or tables."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Grant a deployed app's service principal Unity Catalog access."
    )
    parser.add_argument(
        "--service-principal",
        required=True,
        help="App service principal client id (UUID). Get it via: "
        "databricks apps get <app-name> --output json | jq -r '.service_principal_client_id'",
    )
    parser.add_argument(
        "--catalog",
        default=os.getenv("AKZO_CATALOG"),
        help="Unity Catalog holding the schemas (default: AKZO_CATALOG from env).",
    )
    parser.add_argument(
        "--tools-schema",
        default=os.getenv("AKZO_TOOLS_SCHEMA", "akzo_tools"),
        help="Schema with the UC-function tools (default: AKZO_TOOLS_SCHEMA or 'akzo_tools').",
    )
    parser.add_argument(
        "--data-schema",
        action="append",
        default=[],
        help="Schema whose tables the functions read (SELECT). Repeatable. "
        "Defaults to the tools schema if none given.",
    )
    args = parser.parse_args()

    if not args.catalog:
        print(
            "Error: no catalog. Pass --catalog <name> or set AKZO_CATALOG in your env.",
            file=sys.stderr,
        )
        sys.exit(1)

    catalog = _validate_ident("catalog", args.catalog)
    tools_schema = _validate_ident("tools-schema", args.tools_schema)
    data_schemas = [_validate_ident("data-schema", s) for s in args.data_schema] or [tools_schema]
    sp = args.service_principal
    if not _IDENT.fullmatch(sp.replace("-", "")):
        print(f"Error: service principal {sp!r} is not a valid client id.", file=sys.stderr)
        sys.exit(1)

    grant_app_access(sp, catalog, tools_schema, data_schemas)


if __name__ == "__main__":
    main()

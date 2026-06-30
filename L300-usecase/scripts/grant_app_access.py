"""Grant the Databricks App service principal the access the supervisor needs.

The supervisor app runs as a service principal (SP). For the read plane (the three domain
legs) and the act plane (the governed HTTP connection) to work under that SP, it needs Unity
Catalog grants on the coatings catalog + schemas, USE CONNECTION on the external-systems
connection, and CAN RUN on each domain's Genie space. This script applies all of them.

Nothing is hardcoded: the SP and the catalog are PARAMETERS. Run after the data + Lakebase
setup, before (or just after) deploying the app:

    uv run grant-app-access --sp <app-sp-application-id> --catalog <your_catalog>

    # or with explicit overrides:
    uv run grant-app-access \
        --sp 1234abcd-... \
        --catalog akzo_workshop \
        --finance-schema akzo_finance --scm-schema akzo_scm --commercial-schema akzo_commercial \
        --connection akzo_external_systems

Genie space ids are read from the environment (FINANCE_SPACE_ID / SCM_SPACE_ID /
COMMERCIAL_SPACE_ID, e.g. from .env); pass --skip-genie to skip the Genie grants entirely.

The UC grants run as governed SQL on the serverless warehouse (DATABRICKS_WAREHOUSE_ID), so
the identity running this script must itself have grant authority on those objects. Genie
grants use the SDK permissions API and are best-effort: if the SDK surface is unavailable the
script prints the manual step instead of failing.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# Reuse the shared backend so the warehouse id / auth resolve exactly as the app does.
sys.path.insert(0, "agent_server")

import databricks_client as dbx  # noqa: E402

_IDENT = re.compile(r"[A-Za-z0-9_]+")
_DOMAINS = ("FINANCE", "SCM", "COMMERCIAL")


def _ident(name: str, value: str) -> str:
    """Reject anything that is not a bare SQL identifier (no injection via --catalog etc.)."""
    if not _IDENT.fullmatch(value):
        raise SystemExit(f"Unsafe {name}: {value!r} — expected a bare identifier [A-Za-z0-9_].")
    return value


def _principal_sql(sp: str) -> str:
    """Quote the principal for a GRANT TO clause (SPs are granted by their backtick name)."""
    return f"`{sp}`"


def _grant_uc(sp: str, catalog: str, schemas: list[str], connection: str | None) -> None:
    principal = _principal_sql(sp)
    stmts: list[str] = [
        f"GRANT USE CATALOG ON CATALOG {catalog} TO {principal}",
    ]
    for schema in schemas:
        fq = f"{catalog}.{schema}"
        stmts += [
            f"GRANT USE SCHEMA ON SCHEMA {fq} TO {principal}",
            f"GRANT SELECT ON SCHEMA {fq} TO {principal}",
        ]
    if connection:
        # USE CONNECTION on the UC connection is what lets the governed http_request() path run.
        # (EXECUTE is not a valid privilege on a CONNECTION entity.)
        stmts.append(f"GRANT USE CONNECTION ON CONNECTION {connection} TO {principal}")

    for stmt in stmts:
        dbx.run_sql(stmt)
        print(f"  ok: {stmt}")


def _grant_genie(sp: str) -> None:
    """CAN RUN on each configured Genie space via the permissions REST API.

    The typed SDK surface for Genie-space permissions varies across versions (older clients
    have no ``genie.set_permissions``), so we PATCH the generic permissions endpoint
    directly — it is stable: PATCH /api/2.0/permissions/genie/{space_id}."""
    space_ids = {d: os.environ.get(f"{d}_SPACE_ID", "").strip() for d in _DOMAINS}
    configured = {d: s for d, s in space_ids.items() if s}
    if not configured:
        print("  (no *_SPACE_ID set in the environment — skipping Genie grants)")
        return

    w = dbx.client()
    for domain, space_id in configured.items():
        try:
            w.api_client.do(
                "PATCH",
                f"/api/2.0/permissions/genie/{space_id}",
                body={
                    "access_control_list": [
                        {"service_principal_name": sp, "permission_level": "CAN_RUN"}
                    ]
                },
            )
            print(f"  ok: {domain} Genie space {space_id} -> CAN_RUN for {sp}")
        except Exception as e:  # noqa: BLE001 — fall back to the manual instruction.
            _print_genie_manual({domain: space_id}, sp, reason=str(e))


def _print_genie_manual(spaces: dict[str, str], sp: str, reason: str) -> None:
    print(f"  note: could not set Genie permissions via SDK ({reason[:160]}).")
    print("  Grant manually in each Genie space's Share dialog (or via the API):")
    for domain, space_id in spaces.items():
        print(f"    - {domain}: space {space_id} -> add '{sp}' with 'Can run'")


def main() -> None:
    p = argparse.ArgumentParser(description="Grant the app SP UC + Genie access for the supervisor.")
    p.add_argument("--sp", required=True,
                   help="App service principal (application id or SP name) to grant access to.")
    p.add_argument("--catalog", default=os.environ.get("AKZO_CATALOG", ""),
                   help="Unity Catalog holding the coatings schemas (or set AKZO_CATALOG).")
    p.add_argument("--finance-schema", default=os.environ.get("AKZO_FINANCE_SCHEMA", "akzo_finance"))
    p.add_argument("--scm-schema", default=os.environ.get("AKZO_SCM_SCHEMA", "akzo_scm"))
    p.add_argument("--commercial-schema",
                   default=os.environ.get("AKZO_COMMERCIAL_SCHEMA", "akzo_commercial"))
    p.add_argument("--connection", default=os.environ.get("AKZO_HTTP_CONNECTION", "akzo_external_systems"),
                   help="UC HTTP connection to grant USE CONNECTION on (empty string to skip).")
    p.add_argument("--skip-genie", action="store_true", help="Skip the Genie space grants.")
    args = p.parse_args()

    if not args.catalog:
        raise SystemExit("--catalog is required (or set AKZO_CATALOG). It is never hardcoded.")

    catalog = _ident("catalog", args.catalog)
    schemas = [
        _ident("finance-schema", args.finance_schema),
        _ident("scm-schema", args.scm_schema),
        _ident("commercial-schema", args.commercial_schema),
    ]
    connection = _ident("connection", args.connection) if args.connection else None
    sp = args.sp.strip()
    if not sp:
        raise SystemExit("--sp is required (the app service principal). It is never hardcoded.")

    print(f"Granting UC access on catalog '{catalog}' to SP '{sp}' ...")
    _grant_uc(sp, catalog, schemas, connection)

    if args.skip_genie:
        print("Skipping Genie grants (--skip-genie).")
    else:
        print("Granting CAN RUN on the domain Genie spaces ...")
        _grant_genie(sp)

    print("Done. The app SP can now read the coatings schemas and run the governed action path.")


if __name__ == "__main__":
    main()

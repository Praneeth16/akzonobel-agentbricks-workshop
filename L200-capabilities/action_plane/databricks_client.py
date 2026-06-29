"""Thin Databricks SDK + SQL-warehouse helper used by the connectors.

`run_sql` executes a statement on a serverless SQL warehouse and returns
`{"rows": [ {col: value, ...}, ... ]}`. The warehouse is discovered from the
environment — nothing is hardcoded:

    DATABRICKS_WAREHOUSE_ID   optional; the first available SQL warehouse is used
                              if unset (handy on a Vocareum lab)
"""
from __future__ import annotations

import logging
import os

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

logger = logging.getLogger(__name__)

_client: WorkspaceClient | None = None
_warehouse_id: str | None = None


def client() -> WorkspaceClient:
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def current_user() -> str:
    return client().current_user.me().user_name


def _resolve_warehouse_id() -> str:
    global _warehouse_id
    if _warehouse_id:
        return _warehouse_id
    env = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    if env:
        _warehouse_id = env
        return _warehouse_id
    # Discover the first warehouse so the lab does not have to set the id.
    # By design (matches the repo's data/ convention) — log clearly so it is not silent.
    for wh in client().warehouses.list():
        _warehouse_id = wh.id
        logger.info(
            "DATABRICKS_WAREHOUSE_ID not set; auto-selected SQL warehouse "
            "'%s' (%s). Set DATABRICKS_WAREHOUSE_ID to pin a specific warehouse.",
            wh.name, wh.id,
        )
        return _warehouse_id
    raise RuntimeError(
        "No SQL warehouse found. Set DATABRICKS_WAREHOUSE_ID to a warehouse you can use."
    )


def run_sql(sql: str) -> dict:
    """Execute `sql` on a SQL warehouse, return {"rows": [dict, ...]}."""
    resp = client().statement_execution.execute_statement(
        warehouse_id=_resolve_warehouse_id(),
        statement=sql,
        wait_timeout="50s",
    )
    if resp.status and resp.status.state not in (StatementState.SUCCEEDED, None):
        raise RuntimeError(f"SQL failed: {resp.status.state} — {resp.status.error}")
    columns = []
    if resp.manifest and resp.manifest.schema and resp.manifest.schema.columns:
        columns = [c.name for c in resp.manifest.schema.columns]
    rows = []
    if resp.result and resp.result.data_array:
        for raw in resp.result.data_array:
            rows.append({columns[i]: raw[i] for i in range(len(columns))})
    return {"rows": rows}

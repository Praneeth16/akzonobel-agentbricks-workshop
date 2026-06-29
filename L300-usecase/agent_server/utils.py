"""Workspace-portable configuration for the L300 Multi-domain Supervisor.

Every value comes from the environment with a safe default, so nothing is tied to one
workspace, catalog, profile, warehouse, or Lakebase instance. The same code runs
unchanged on a lab workspace (e.g. Vocareum) or your own.

Resolution order for the catalog: ``AKZO_CATALOG`` env > Spark ``current_catalog()`` >
the ``main`` fallback (local/offline). The three domain schemas default to
``akzo_finance`` / ``akzo_scm`` / ``akzo_commercial`` under that catalog.

Env vars (all optional unless noted):
    AKZO_CATALOG            Unity Catalog holding the coatings data. Falls back to
                            current_catalog(); REQUIRED if Spark can't resolve one (no default).
    AKZO_FINANCE_SCHEMA     Finance schema.    Default: "akzo_finance".
    AKZO_SCM_SCHEMA         Supply-chain schema. Default: "akzo_scm".
    AKZO_COMMERCIAL_SCHEMA  Commercial schema. Default: "akzo_commercial".
    LLM_ENDPOINT            Chat model serving endpoint. REQUIRED — no hardcoded model default.
    DATABRICKS_WAREHOUSE_ID Serverless SQL warehouse for governed reads. No default (required for SQL legs).
    DATABRICKS_HOST         Workspace URL. Default: resolved from the Databricks SDK config.
    FINANCE_SPACE_ID / SCM_SPACE_ID / COMMERCIAL_SPACE_ID
                            Real Genie space ids. When set, that domain leg calls the real
                            Genie space; when blank, it falls back to instruction-driven text2sql.
    LAKEBASE_INSTANCE       Lakebase (managed Postgres) instance name for the audit/memory tables.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

DEFAULT_SCHEMAS = {
    "FINANCE": "akzo_finance",
    "SCM": "akzo_scm",
    "COMMERCIAL": "akzo_commercial",
}

_IDENT = re.compile(r"[A-Za-z0-9_]+")
_ENDPOINT = re.compile(r"[A-Za-z0-9_.-]+")


def _validate(name: str, value: str, pattern: re.Pattern) -> str:
    """Reject values unsafe to interpolate into SQL or a URL path."""
    if not pattern.fullmatch(value):
        raise ValueError(f"Unsafe {name}: {value!r}.")
    return value


def get_current_catalog() -> Optional[str]:
    """Return the workspace's current catalog via Spark, or None if unavailable."""
    try:
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        return spark.sql("SELECT current_catalog()").first()[0]
    except Exception as e:  # noqa: BLE001 — local/offline use has no Spark
        logging.debug("current_catalog() unavailable: %s", e)
        return None


def get_catalog() -> str:
    """Resolve the catalog: AKZO_CATALOG env > current_catalog(). Fails fast if neither.

    No silent fallback to a placeholder catalog (e.g. 'main'): a wrong catalog would read the
    wrong data, so we refuse rather than guess. Set AKZO_CATALOG, or run where Spark can
    resolve current_catalog() (e.g. on a lab such as Vocareum)."""
    catalog = os.environ.get("AKZO_CATALOG") or get_current_catalog()
    if not catalog:
        raise RuntimeError(
            "Catalog unresolved: set AKZO_CATALOG, or run where Spark current_catalog() is "
            "available. There is no default catalog — guessing would read the wrong data."
        )
    return _validate("catalog", catalog, _IDENT)


def get_schema(domain: str) -> str:
    """Return the fully qualified ``catalog.schema`` for a domain (FINANCE/SCM/COMMERCIAL)."""
    env_key = f"AKZO_{domain}_SCHEMA"
    schema = os.environ.get(env_key, DEFAULT_SCHEMAS[domain])
    return f"{get_catalog()}.{_validate('schema', schema, _IDENT)}"


def get_llm_endpoint() -> str:
    """Resolve the chat model serving endpoint name from LLM_ENDPOINT. Fails fast if unset.

    No hardcoded model default: the entitled endpoint differs per lab/workspace, so the
    workshop sets it explicitly (matching L100/L200)."""
    endpoint = os.environ.get("LLM_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "LLM_ENDPOINT is not set — set it in .env / app.yaml to your entitled chat model "
            "serving endpoint (e.g. a Foundation Model API endpoint). There is no default."
        )
    return _validate("LLM endpoint", endpoint, _ENDPOINT)


def get_databricks_host() -> Optional[str]:
    """Resolve the workspace host from env or the Databricks SDK config."""
    host = os.environ.get("DATABRICKS_HOST")
    if host:
        return host.rstrip("/")
    try:
        from databricks.sdk import WorkspaceClient

        return WorkspaceClient().config.host
    except Exception as e:  # noqa: BLE001
        logging.debug("Could not resolve Databricks host: %s", e)
        return None


def get_space_id(domain: str) -> str:
    """Real Genie space id for a domain, from <DOMAIN>_SPACE_ID env. Empty when unset."""
    return os.environ.get(f"{domain}_SPACE_ID", "").strip()


def get_genie_mcp_url(domain: str) -> Optional[str]:
    """Managed MCP Genie server URL for a domain, or None if host/space id missing.

    Pattern (Public Preview): {host}/api/2.0/mcp/genie/{space_id}
    """
    host = get_databricks_host()
    space_id = get_space_id(domain)
    if not host or not space_id:
        return None
    return f"{host}/api/2.0/mcp/genie/{space_id}"

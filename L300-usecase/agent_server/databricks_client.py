"""Databricks SDK access — the shared backend module for the supervisor + its legs.

Provides:
  - a process-wide WorkspaceClient singleton (auths via the app service principal in
    Databricks Apps, or via the CLI profile ``DATABRICKS_CONFIG_PROFILE`` locally),
  - ``run_sql(...)`` — execute governed Spark SQL on the serverless SQL warehouse and
    return {columns, rows, row_count} with rows as list-of-dicts,
  - ``chat(...)``    — query a Databricks Model Serving chat endpoint (OpenAI-style messages).

Nothing here is hardcoded to a workspace: the warehouse id and chat endpoint come from
the environment (``DATABRICKS_WAREHOUSE_ID`` / ``LLM_ENDPOINT``), so the same code runs
unchanged on any lab workspace (e.g. Vocareum) or your own.
"""
from __future__ import annotations

import os
import threading
from functools import lru_cache
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

# No hardcoded defaults — resolved from the environment. SQL legs require a warehouse id.
SQL_WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")


def _chat_endpoint() -> str:
    """The chat model serving endpoint, from LLM_ENDPOINT (or legacy DATABRICKS_CHAT_ENDPOINT).
    Fails fast if unset — there is no hardcoded model default (matches L100/L200 + utils)."""
    endpoint = os.environ.get("LLM_ENDPOINT") or os.environ.get("DATABRICKS_CHAT_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "LLM_ENDPOINT is not set — set it in .env / app.yaml to your entitled chat model "
            "serving endpoint. There is no default."
        )
    return endpoint

_lock = threading.Lock()
_client: WorkspaceClient | None = None


def client() -> WorkspaceClient:
    """Return the process-wide WorkspaceClient singleton (thread-safe)."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = WorkspaceClient()
    return _client


@lru_cache(maxsize=1)
def current_user() -> str:
    """The identity the SDK is authenticating as (email)."""
    return client().current_user.me().user_name


def run_sql(statement: str, warehouse_id: str | None = None, wait_timeout: str = "50s",
            w=None) -> dict[str, Any]:
    """Execute governed SQL on the serverless warehouse.

    Returns {"columns": [..], "rows": [{col: val, ...}, ...], "row_count": n}.
    Raises RuntimeError on a non-SUCCEEDED terminal state or a missing warehouse id.

    ``w`` is the WorkspaceClient the statement runs under. Pass the end user's OBO client so
    the read executes under the caller's Unity Catalog identity (row filters / column masks
    apply). When ``w`` is None the process service-principal client is used — appropriate
    only for non-user-scoped reads, never as a governance fallback for a user request.
    """
    wh = warehouse_id or SQL_WAREHOUSE_ID
    if not wh:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set — set it in app.yaml / .env to run governed SQL legs."
        )
    resp = (w or client()).statement_execution.execute_statement(
        warehouse_id=wh, statement=statement, wait_timeout=wait_timeout,
    )
    state = resp.status.state.value if resp.status and resp.status.state else "UNKNOWN"
    if state != "SUCCEEDED":
        msg = resp.status.error.message if resp.status and resp.status.error else state
        raise RuntimeError(f"SQL execution {state}: {msg}")

    columns: list[str] = []
    if resp.manifest and resp.manifest.schema and resp.manifest.schema.columns:
        columns = [c.name for c in resp.manifest.schema.columns]

    data = (resp.result.data_array if resp.result else None) or []
    rows = [dict(zip(columns, raw)) for raw in data]
    return {"columns": columns, "rows": rows, "row_count": len(rows)}


def chat(messages: list[dict[str, str]], endpoint: str | None = None,
         max_tokens: int = 1024, temperature: float | None = None) -> str:
    """Query a Model Serving chat endpoint. ``messages`` is OpenAI-style
    [{"role": "system"|"user"|"assistant", "content": str}, ...]. Returns text.

    Note: some endpoints reject the ``temperature`` parameter, so it is only sent when
    explicitly provided."""
    role_map = {
        "system": ChatMessageRole.SYSTEM,
        "user": ChatMessageRole.USER,
        "assistant": ChatMessageRole.ASSISTANT,
    }
    chat_messages = [ChatMessage(role=role_map[m["role"]], content=m["content"]) for m in messages]
    kwargs: dict[str, Any] = {"name": endpoint or _chat_endpoint(), "messages": chat_messages,
                              "max_tokens": max_tokens}
    if temperature is not None:
        kwargs["temperature"] = temperature
    resp = client().serving_endpoints.query(**kwargs)
    return resp.choices[0].message.content

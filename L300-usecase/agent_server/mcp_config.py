"""MCP fleet wiring for the Multi-domain Supervisor.

The supervisor reaches its governed tools over the Model Context Protocol (MCP). This module
enumerates the full fleet as Databricks *managed* MCP servers, built from the environment so
nothing is hardcoded to one workspace:

  - one Genie MCP server per domain (Finance / SCM / Commercial), pattern
    ``{host}/api/2.0/mcp/functions``-style ``{host}/api/2.0/mcp/genie/{space_id}``;
  - the system AI functions server ``{host}/api/2.0/mcp/functions/system/ai``;
  - optionally a vector-search server for document tools, ``{host}/api/2.0/mcp/vector-search/{index}``.

``fleet()`` returns the list of ``DatabricksMCPServer`` objects for the configured surface;
servers whose id/index is unset are skipped (logged), so a partially-configured lab still runs.

The supervisor's read plane in ``supervisor.py`` calls Genie via the Conversation API directly
(so it gets the SQL + rows for the trace), and ``agent.py`` exposes that as the
``ask_supervisor`` tool. This module is the alternative/native wiring: register these servers
on a LangGraph agent (``DatabricksMultiServerMCPClient(fleet()).get_tools()``) to let the model
call each Genie space as a first-class MCP tool. Both paths are governed by Unity Catalog.
"""
from __future__ import annotations

import logging
import os

from agent_server.utils import get_databricks_host, get_space_id

logger = logging.getLogger(__name__)

DOMAINS = ("FINANCE", "SCM", "COMMERCIAL")


def genie_server_urls() -> dict[str, str]:
    """domain -> managed Genie MCP URL, for each domain whose space id is set."""
    host = get_databricks_host()
    urls: dict[str, str] = {}
    if not host:
        logger.warning("Databricks host unresolved — no Genie MCP servers wired.")
        return urls
    for d in DOMAINS:
        space_id = get_space_id(d)
        if space_id:
            urls[d] = f"{host}/api/2.0/mcp/genie/{space_id}"
        else:
            logger.warning("%s_SPACE_ID not set — %s Genie MCP server skipped.", d, d)
    return urls


def system_ai_url() -> str | None:
    """Managed MCP server for the system AI functions (built-in tools)."""
    host = get_databricks_host()
    return f"{host}/api/2.0/mcp/functions/system/ai" if host else None


def vector_search_url() -> str | None:
    """Managed MCP vector-search server for document tools, if VECTOR_SEARCH_INDEX is set.

    Index format: ``<catalog>/<schema>/<index>`` (a dotted value from Apps valueFrom injection
    is normalized to slashes).
    """
    host = get_databricks_host()
    raw = os.environ.get("VECTOR_SEARCH_INDEX", "")
    if not host or not raw:
        return None
    index = raw.replace(".", "/") if "." in raw and "/" not in raw else raw
    return f"{host}/api/2.0/mcp/vector-search/{index}"


def fleet():
    """Return the configured fleet as a list of ``DatabricksMCPServer`` objects.

    Requires ``databricks_langchain`` (only needed when wiring MCP natively). Servers with
    unset ids/index are skipped so a partial lab still works.
    """
    from databricks.sdk import WorkspaceClient
    from databricks_langchain import DatabricksMCPServer

    w = WorkspaceClient()
    servers = []
    if (url := system_ai_url()):
        servers.append(DatabricksMCPServer(name="system-ai", url=url, workspace_client=w))
    for domain, url in genie_server_urls().items():
        servers.append(
            DatabricksMCPServer(name=f"{domain.lower()}-genie", url=url, workspace_client=w)
        )
    if (url := vector_search_url()):
        servers.append(DatabricksMCPServer(name="coatings-docs", url=url, workspace_client=w))
    return servers

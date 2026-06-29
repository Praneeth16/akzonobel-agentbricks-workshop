"""L200 coded agent — OpenAI Agents SDK, served as an MLflow ResponsesAgent.

This is the AkzoNobel L200 capability agent. It keeps the OpenAI Agents SDK
framework from the L100 reference, and adds what L200 is about: it calls
Unity Catalog function tools through the managed UC-functions MCP server, and
(via actions_api) it can propose governed actions that a human must approve.

EVERYTHING here is parametrized — nothing is tied to one workspace:

  AGENT_NAME            display name of the agent (default: akzo-capabilities-agent)
  LLM_ENDPOINT          serving endpoint / model (REQUIRED — no default; fails fast if unset)
  AKZO_CATALOG          Unity Catalog holding the akzo_* schemas (required for tools)
  AKZO_TOOLS_SCHEMA     schema holding the UC-function tools (default: akzo_tools)
  AKZO_GENIE_SPACE_ID   optional Genie space id to attach as a tool
  AKZO_MCP_SERVERS      optional extra MCP servers, as "name|path" pairs, ';'-separated

The MCP server list is built at startup from those env vars, so a Vocareum lab
attaches its own catalog and Genie space without editing this file.
"""

import logging
import os

from agents.mcp import MCPServer, MCPServerManager
from typing import AsyncGenerator, List

import mlflow
from agents import Agent, Runner, set_default_openai_api, set_default_openai_client
from agents.tracing import set_trace_processors
from databricks_openai import AsyncDatabricksOpenAI
from databricks_openai.agents import McpServer
from fastapi import HTTPException
from mlflow.genai.agent_server import invoke, stream
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.utils import (
    build_mcp_url,
    create_session,
    deduplicate_input,
    get_session_id,
    get_user_workspace_client,
    init_lakebase_config,
    process_agent_stream_events,
)

logger = logging.getLogger(__name__)

# NOTE: this will work for all databricks models OTHER than GPT-OSS, which uses a slightly different API
# STARTUP RESILIENCE: building the OpenAI client / enabling autolog can touch ambient auth.
# Never let that crash the server at import — the app must always boot so it can surface
# errors per-request instead of failing to start (Databricks Apps health check fails on a
# dead boot). Anything that did not initialize is retried lazily on the first request.
try:
    set_default_openai_client(AsyncDatabricksOpenAI())
    set_default_openai_api("chat_completions")
    set_trace_processors([])  # only use mlflow for trace processing
    mlflow.openai.autolog()
except Exception as e:  # noqa: BLE001
    logger.warning(
        "Could not fully initialize the OpenAI client / tracing at import (%s); "
        "the server will still start and retry lazily per request.", e,
    )

NAME = os.environ.get("AGENT_NAME", "akzo-capabilities-agent")

# LLM_ENDPOINT is required — never a code default. Set it explicitly per deploy
# (app.yaml / databricks.yml) so the agent is not silently tied to one model.
# DO NOT raise at import: a missing env var must not crash the app server at boot.
# We surface a clear 400 per-request instead (see _require_model), so the app starts,
# passes its health check, and an operator can read the error in the app logs.
MODEL = os.environ.get("LLM_ENDPOINT")
if not MODEL:
    logger.warning(
        "LLM_ENDPOINT is not set. The server will start, but every request will fail "
        "until you set it to a serving endpoint you are entitled to (in .env for local "
        "runs, or in app.yaml / databricks.yml for deploys). It has no default so the "
        "agent is never tied to one workspace's model."
    )


def _require_model() -> str:
    """Return the configured model endpoint, or raise a clear per-request error."""
    if not MODEL:
        raise HTTPException(
            status_code=400,
            detail=(
                "LLM_ENDPOINT is not set. Set it to a serving endpoint you are entitled "
                "to (app.yaml / databricks.yml config env) and restart the app."
            ),
        )
    return MODEL

SYSTEM_PROMPT = (
    "You are the AkzoNobel Capabilities Agent. You help analysts answer questions "
    "about coatings Finance, Supply Chain, and Commercial data.\n"
    "Use the Unity Catalog function tools to look up facts; never invent numbers. "
    "If a tool returns nothing, say so plainly rather than guessing.\n"
    "When the user asks you to send a notification or open a ticket, do NOT act "
    "directly. Propose the action through the Action Plane (the /api/act endpoint) "
    "so a human can approve it first. All data is synthetic workshop data."
)


def _build_mcp_servers() -> list[tuple[str, str]]:
    """Construct the (name, path-or-url) MCP server list from the environment.

    The UC-functions MCP server is the L200 default: it exposes every function in
    AKZO_CATALOG.AKZO_TOOLS_SCHEMA as an agent tool. An optional Genie space and
    any extra servers in AKZO_MCP_SERVERS are appended.
    """
    servers: list[tuple[str, str]] = []

    catalog = os.environ.get("AKZO_CATALOG")
    tools_schema = os.environ.get("AKZO_TOOLS_SCHEMA", "akzo_tools")
    if catalog:
        servers.append(
            (
                f"UC Functions: {catalog}.{tools_schema}",
                f"/api/2.0/mcp/functions/{catalog}/{tools_schema}",
            )
        )
    else:
        logger.warning(
            "AKZO_CATALOG is not set — the agent will start with no UC-function "
            "tools. Set AKZO_CATALOG (and optionally AKZO_TOOLS_SCHEMA) to enable them."
        )

    genie_space = os.environ.get("AKZO_GENIE_SPACE_ID")
    if genie_space:
        servers.append((f"Genie Space: {genie_space}", f"/api/2.0/mcp/genie/{genie_space}"))

    extra = os.environ.get("AKZO_MCP_SERVERS", "").strip()
    if extra:
        for entry in extra.split(";"):
            entry = entry.strip()
            if not entry or "|" not in entry:
                continue
            name, path = (part.strip() for part in entry.split("|", 1))
            servers.append((name, path))

    return servers


MCP_SERVERS = _build_mcp_servers()

lakebase_config = init_lakebase_config()


def get_mcp_user_workspace_client():
    # Uncomment to authenticate MCP calls on-behalf-of the signed-in user.
    # return get_user_workspace_client()
    return None


def init_mcp_servers():
    user_workspace_client = get_mcp_user_workspace_client()
    return [
        McpServer(
            name=name,
            url=build_mcp_url(url, user_workspace_client),
            workspace_client=user_workspace_client,
        )
        for (name, url) in MCP_SERVERS
    ]


def create_agent(mcp_servers: List[MCPServer]) -> Agent:
    return Agent(
        name=NAME,
        instructions=SYSTEM_PROMPT,
        model=_require_model(),
        mcp_servers=mcp_servers,
    )


@invoke()
async def invoke(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    session_id = get_session_id(request)
    session = None

    if lakebase_config:
        session = create_session(session_id, lakebase_config)
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})

    try:
        mcp_servers = init_mcp_servers()
        async with MCPServerManager(servers=mcp_servers, connect_in_parallel=True) as manager:
            agent = create_agent(manager.active_servers)

            if session:
                messages = await deduplicate_input(request, session)
            else:
                messages = [i.model_dump() for i in request.input]

            result = await Runner.run(agent, messages, session=session)
            return ResponsesAgentResponse(
                output=[item.to_input_item() for item in result.new_items],
                custom_outputs={"session_id": session.session_id} if session else None,
            )
    except Exception as e:
        error_msg = str(e).lower()
        if any(kw in error_msg for kw in ["lakebase", "pg_hba", "postgres", "database instance"]):
            logger.error("Lakebase access error: %s", e)
            raise HTTPException(status_code=503, detail=f"Lakebase unavailable: {e}") from e
        raise


@stream()
async def stream(request: ResponsesAgentRequest) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    session_id = get_session_id(request)
    session = None

    if lakebase_config:
        session = create_session(session_id, lakebase_config)
        mlflow.update_current_trace(metadata={"mlflow.trace.session": session_id})

    mcp_servers = init_mcp_servers()
    async with MCPServerManager(servers=mcp_servers, connect_in_parallel=True) as manager:
        agent = create_agent(manager.active_servers)

        if session:
            messages = await deduplicate_input(request, session)
        else:
            messages = [i.model_dump() for i in request.input]

        result = Runner.run_streamed(agent, input=messages, session=session)

        async for event in process_agent_stream_events(result.stream_events()):
            yield event

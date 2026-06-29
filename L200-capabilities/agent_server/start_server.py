import asyncio
import logging
import os
from pathlib import Path

from databricks_openai.agents.session import AsyncDatabricksSession
from dotenv import load_dotenv
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

from agent_server.utils import init_lakebase_config

logger = logging.getLogger(__name__)

# Load env vars from .env before importing the agent for proper auth
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)


async def _ensure_lakebase_tables() -> None:
    config = init_lakebase_config()
    if not config:
        return
    try:
        session = AsyncDatabricksSession(
            session_id="__startup__",
            instance_name=config.instance_name,
            autoscaling_endpoint=config.autoscaling_endpoint,
            project=config.autoscaling_project,
            branch=config.autoscaling_branch,
            schema=config.memory_schema,
        )
        await session._ensure_tables()
        logger.info("Lakebase tables ready (schema: %s)", config.memory_schema)
    except Exception as e:
        logger.warning("Could not create Lakebase tables at startup: %s", e)


# Need to import the agent to register the @invoke/@stream functions with the server
import agent_server.agent  # noqa: E402

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
# Define the app as a module level variable to enable multiple workers
app = agent_server.app  # noqa: F841
setup_mlflow_git_based_version_tracking()

# Mount the Action Plane HTTP API (propose / approve / execute) on the same app,
# so the agent's proposed actions and a human's approvals share one process.
# Disabled by default; enable by setting ENABLE_ACTIONS_API=true once a Lakebase
# instance with the actions schema is configured (see action_plane/README).
if os.environ.get("ENABLE_ACTIONS_API", "").lower() in ("1", "true", "yes"):
    try:
        from agent_server.actions_api import build_actions_router

        app.include_router(build_actions_router(os.environ.get("AGENT_NAME", "akzo-capabilities-agent")))
        logger.info("Action Plane API mounted under /api")
    except Exception as e:
        logger.warning("Could not mount Action Plane API: %s", e)

# Run memory table creation at startup
try:
    asyncio.run(_ensure_lakebase_tables())
except Exception as e:
    logger.warning("Lakebase table setup deferred: %s", e)


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")

"""MLflow ResponsesAgent server entry point for the Multi-domain Supervisor.

Wraps ``agent_server.agent.AGENT`` in the MLflow agent server so the supervisor is served
over the Responses API (streaming, tracing, evaluation) — the same serving surface the L100
and L200 agents use. Run with ``uv run start-app`` (see pyproject ``[project.scripts]``).
"""
from dotenv import load_dotenv
from mlflow.genai.agent_server import AgentServer, setup_mlflow_git_based_version_tracking

# Load env vars from .env before importing the agent for proper auth.
load_dotenv(dotenv_path=".env", override=True)

# Import the agent to register it with the server.
import agent_server.agent  # noqa: E402,F401

agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)

# Module-level app variable to enable multiple workers.
app = agent_server.app  # noqa: F841
try:
    setup_mlflow_git_based_version_tracking()
except Exception:
    pass  # Non-fatal: skip git-based tracking if it fails (e.g. not a git repo).


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")

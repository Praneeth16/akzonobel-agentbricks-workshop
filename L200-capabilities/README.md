# L200: Capabilities, a coded agent that uses tools and acts

You have called AI from SQL and built the no code Agent Bricks types in L100. Now you write a real agent: an OpenAI Agents SDK agent that calls Unity Catalog function tools through an MCP server you build, remembers across turns on Lakebase, deploys as a Databricks App, and proposes real world actions that a human approves before they run.

---

## What You Will Build

| Capability | Powered By |
|---|---|
| A coded agent with tool calling | OpenAI Agents SDK, served as an MLflow `ResponsesAgent` |
| Tools from your data | Unity Catalog functions exposed through the UC functions MCP server |
| An MCP server you build and register | UC function MCP server, discovered with `discover-tools` |
| Memory across turns and sessions | Lakebase (managed Postgres) |
| The first agent that acts | Action Plane: email and ticket connectors, behind human approval |
| A multi judge evaluation suite plus governance | MLflow correctness and groundedness judges, AI Gateway |
| A deployed app | Databricks Apps via Asset Bundles |

---

## The Three Spines (and where L200 sits)

| Spine | L200 (here) |
|---|---|
| Agent Bricks types | Add Unity Catalog function tools to a coded agent (OpenAI Agents SDK) |
| MCP | Build and register an MCP server, then consume it from the agent |
| Agents that act | One or two connectors (email, ticket) with guardrails and human approval. Every action stops at `proposed` until a human approves |
| LLMOps | Judge suite (correctness and groundedness), AI Gateway, and an audit trail over every proposed action |

---

## Get Started

Work through the materials in order. Read the **quickstart** and **discover-tools** skills first if you are using an AI coding assistant.

1. **Discover tools.** `uv run discover-tools --catalog $AKZO_CATALOG` shows the UC functions, Genie spaces, and indexes you can wire in.
2. **Run the agent locally.** Set `AKZO_CATALOG` and `LLM_ENDPOINT` in `.env`, then `uv run start-app`. The agent calls every function in your tools schema through the UC functions MCP server.
3. **Add memory.** Set a Lakebase instance in `.env` and run `scripts/lakebase_setup_script.ipynb`. See the **agent-memory** skill.
4. **Turn on actions.** Run `scripts/actions_schema_setup.py`, set `ENABLE_ACTIONS_API=true`, and the agent can propose email and ticket actions through the Action Plane. See `action_plane/README.md`.
5. **Evaluate.** Open `agent_evaluation.ipynb` to run the correctness and groundedness judge suite and configure AI Gateway.
6. **Deploy.** Follow the **deploy** skill to ship the agent as a Databricks App.

The shared data setup in the repo root `data/` folder must run once before this tier.

---

## Everything Is Parametrized

Nothing here is tied to one workspace. The agent reads its catalog, model endpoint, MCP servers, and Lakebase instance from environment variables; the bundle takes them as deploy time variables. On a Vocareum lab you set your assigned catalog and instance and nothing else changes.

| What | Where it comes from |
|---|---|
| Unity Catalog | `AKZO_CATALOG` env / `catalog` bundle var (no default workspace) |
| LLM endpoint | `LLM_ENDPOINT` env / `llm_endpoint` bundle var |
| Tools schema | `AKZO_TOOLS_SCHEMA` env (default `akzo_tools`) |
| Genie space | `AKZO_GENIE_SPACE_ID` env (optional) |
| Lakebase instance | `LAKEBASE_INSTANCE_NAME` / `LAKEBASE_INSTANCE` env |
| SQL warehouse | `DATABRICKS_WAREHOUSE_ID` env, or the first warehouse is discovered |
| Mock systems URL | `AKZO_MOCK_SYSTEMS_URL` env (no default URL) |

---

## Folder Contents

| Path | Purpose |
|------|---------|
| `agent_server/agent.py` | The OpenAI Agents SDK agent. Builds its MCP server list from env |
| `agent_server/utils.py` | Lakebase session, MCP URL building, stream processing |
| `agent_server/start_server.py` | FastAPI server, MLflow setup, mounts the Action Plane API |
| `agent_server/actions_api.py` | HTTP routes for the Act, Approve, Execute loop |
| `action_plane/` | The governed action plane: state machine, guardrails, executor, email and ticket connectors |
| `scripts/discover_tools.py` | Discover workspace resources |
| `scripts/lakebase_setup_script.ipynb` | Prepare Lakebase for memory and actions |
| `scripts/actions_schema_setup.py` | Create Action Plane tables and seed L200 policies |
| `scripts/grant_lakebase_permissions.py` | Grant the deployed app's SP access to Lakebase |
| `scripts/app_deployment_script.ipynb` | SDK based deploy alternative to the CLI |
| `agent_evaluation.ipynb` | Judge suite and AI Gateway |
| `tests/test_action_plane.py` | Characterization tests for the state machine and guardrails |
| `app.yaml`, `databricks.yml` | App and bundle configuration |
| `.claude/skills/` | add-tools, discover-tools, lakebase-setup, agent-memory, deploy |

---

## Prerequisites

- Databricks workspace with serverless SQL, Foundation Model API, Unity Catalog, Lakebase, and Databricks Apps enabled
- The shared data setup completed (see `../data/`)
- `uv` for local development, Databricks CLI v0.298.0+ for deploy

---

## Next

Move up to `../L300-usecase/` for the multi domain supervisor, the full L1 to L4 action ladder with all connectors and an approval center, and production monitoring with Unity Catalog lineage.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.

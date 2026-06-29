# Agent Development Guide — L200 Capabilities

This tier is a coded agent: an OpenAI Agents SDK agent (`agent_server/agent.py`) served as an MLflow `ResponsesAgent`, with Unity Catalog function tools via MCP, Lakebase memory, and the Action Plane for governed actions.

## Before you start

1. **Read the skill for the task** in `.claude/skills/` — they hold tested commands and patterns.
2. **Check `.env`.** If it exists, the environment is configured; read `AKZO_CATALOG`, `LLM_ENDPOINT`, and the Lakebase vars. If not, copy `.env.example` and fill in at least `AKZO_CATALOG` and `LLM_ENDPOINT`.
3. **Nothing is workspace-specific.** Never hardcode a catalog, workspace URL, profile, warehouse id, or Lakebase instance. Everything is read from env / bundle variables. This lab runs on Vocareum.

## Available skills

| Task | Skill |
|------|-------|
| Find tools/resources | `.claude/skills/discover-tools/skill.md` |
| Add tools & grant permissions | `.claude/skills/add-tools/skill.md` |
| Lakebase memory + actions setup | `.claude/skills/lakebase-setup/skill.md` |
| Give the agent memory | `.claude/skills/agent-memory/skill.md` |
| Deploy to Databricks Apps | `.claude/skills/deploy/skill.md` |

## Quick commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Discover tools | `uv run discover-tools --catalog $AKZO_CATALOG` |
| Run locally | `uv run start-app` |
| Pre-flight | `uv run preflight` |
| Tests | `uv run pytest tests` |
| Create Action Plane tables | `uv run python scripts/actions_schema_setup.py` |
| Deploy | `databricks bundle deploy && databricks bundle run akzo_capabilities_agent` |

## How tools get wired

The agent builds its MCP server list at startup from env vars (`_build_mcp_servers`):
- `AKZO_CATALOG` + `AKZO_TOOLS_SCHEMA` → UC functions MCP server (every function in that schema becomes a tool).
- `AKZO_GENIE_SPACE_ID` → Genie space tool.
- `AKZO_MCP_SERVERS` → extra `name|path` pairs.

You rarely edit agent code; set env vars and grant permissions in `databricks.yml`. See **add-tools**.

## Agents that act

Actions flow through `action_plane/` — a state machine over Lakebase (`actions`, `action_events`) gated by `evaluate()` guardrails (`action_policies`). At L200 only the **email** and **ticket** connectors are enabled, and every policy has `requires_approval = true`, so an action stops at `proposed` until a human approves via `/api/actions/{id}/approve`. The HTTP routes are in `agent_server/actions_api.py` and are mounted only when `ENABLE_ACTIONS_API=true`.

When changing `evaluate()` or the state machine, run `uv run pytest tests` first — those characterization tests lock in the ported behavior.

## Key files

| File | Purpose |
|------|---------|
| `agent_server/agent.py` | Agent, model, instructions, MCP server list from env |
| `agent_server/utils.py` | Lakebase session, MCP URL, stream processing |
| `agent_server/start_server.py` | Server + MLflow + Action Plane mount |
| `agent_server/actions_api.py` | Act / Approve / Execute HTTP routes |
| `action_plane/model.py` | State machine over Lakebase |
| `action_plane/guardrails.py` | `evaluate()` policy checks |
| `action_plane/executor.py` | Dispatches approved actions to connectors |
| `action_plane/connectors/` | email + ticket connectors |
| `databricks.yml` | Bundle config + resource permissions |

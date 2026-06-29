# AGENTS.md, L300 Multi-domain Supervisor

Guidance for coding agents working in this tier. Read this before editing.

## What this tier is

The flagship use case: a LangGraph supervisor that routes a question across three domain sub-agents (Finance, Supply Chain, Commercial), each backed by a Genie space, fuses one governed answer, and can propose actions through the full Action Plane behind an L1 to L4 approval ladder.

## Architecture, in one breath

`agent.py` (LangGraph `ResponsesAgent`) exposes two tools: `ask_supervisor` and `propose_action`. `ask_supervisor` calls `supervisor.supervise()`, which does route → call domain legs → fuse. Each leg lives in `subagents/` and runs a real Genie space (OBO) or the `text2sql` fallback over the bundled `*_space.md`. `propose_action` stages an action through `action_plane/`, which never executes on its own; the Action Center app approves and executes.

## The golden rule: nothing is hardcoded to a workspace

This workshop runs on Vocareum labs and on people's own workspaces. Every workspace specific value comes from the environment, resolved in `agent_server/utils.py`:

- Catalog: `AKZO_CATALOG` env, else Spark `current_catalog()`, else `main`. Never write a catalog literal.
- Schemas: `AKZO_FINANCE_SCHEMA` / `AKZO_SCM_SCHEMA` / `AKZO_COMMERCIAL_SCHEMA`.
- LLM endpoint: `LLM_ENDPOINT`. Warehouse: `DATABRICKS_WAREHOUSE_ID`.
- Genie spaces: `FINANCE_SPACE_ID` / `SCM_SPACE_ID` / `COMMERCIAL_SPACE_ID`.
- Lakebase: `LAKEBASE_INSTANCE` / `LAKEBASE_DBNAME` / `LAKEBASE_SCHEMA`.
- Mock systems URL: `AKZO_MOCK_SYSTEMS_URL`. HTTP connection: `AKZO_HTTP_CONNECTION`.

Never commit `praneeth`, a workspace host, a warehouse id, or a Lakebase instance name. If you find one, replace it with an env lookup. The space files use the `${AKZO_CATALOG}` placeholder, expanded at read time in `subagents/text2sql.py`.

## How to extend

- **Add or change a domain's routing:** edit the `ROUTING_DESCRIPTION` line in `subagents/finance.py`, `scm.py`, or `commercial.py`. This is the sub-agent description a native Multi-Agent Supervisor reads. Editing it re-routes.
- **Add a fourth domain:** add a `subagents/<domain>.py` (copy `scm.py`, fill in `DOMAIN`, `ROUTING_DESCRIPTION`, `REFRAME_HINT`), drop a `<domain>_space.md` next to it, add it to `REGISTRY` in `subagents/__init__.py`, and add a `<DOMAIN>_SPACE_ID` env var.
- **Add a connector:** add `action_plane/connectors/<name>.py` with a `send(payload) -> {ref_id, system, raw, via}` using `_http.post`, register it in `connectors/__init__.py` `SYSTEMS`, and add a route in `executor.py` `ROUTING`. Add a row to `action_policies` via `seed_action_policies.py`.
- **Change the LLM:** set `LLM_ENDPOINT`. Do not hardcode an endpoint in code.

## Reuse, do not duplicate

The Finance sub-agent is the reused L200 finance copilot leg. The `action_plane` is the same governed plane introduced in L200 and deepened here. The shared backend modules (`databricks_client.py`, `lakebase.py`) are reused by the Action Center backend too. Keep them in sync rather than forking.

## Verifying

- `python3 -c "import ast; ast.parse(open(F).read())"` on any `.py` you change.
- `uv run smoke-supervisor` exercises routing and fusion against the lab.
- The frontend apps (`action-center/`, `e2e-chatbot-app/`) are TypeScript; do not assume a Python lint applies.
- There is no auth in CI here. Do not attempt to run against Databricks without credentials; reason about correctness from the code.

## Style

Minimal, correct code. No speculative abstractions. Match the existing docstring voice: explain why, not what. Keep workshop prose plain and free of jargon.

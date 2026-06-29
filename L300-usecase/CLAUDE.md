# CLAUDE.md, L300 Multi-domain Supervisor

Instructions for Claude Code sessions in this tier. These extend the workspace and repo level instructions; the points below are the ones specific to L300.

See `AGENTS.md` for the full architecture and extension guide. The essentials:

## Non negotiables

- **Never hardcode a workspace value.** Catalog, schemas, LLM endpoint, warehouse id, Genie space ids, Lakebase instance, and the mock systems URL all come from the environment, resolved in `agent_server/utils.py`. This tier runs on Vocareum labs; a hardcoded `praneeth`, host, or warehouse id breaks portability. Use `${AKZO_CATALOG}` in space files (expanded at read time).
- **The supervisor proposes actions; it never executes them.** `propose_action` stages an action in status `proposed`. Approval and execution happen in the Action Center, behind the guardrail engine and the L1 to L4 ladder. Do not add a code path that auto executes outside the Action Plane state machine.
- **Reuse the shared modules.** The Finance leg is the reused L200 finance copilot; `action_plane/`, `databricks_client.py`, and `lakebase.py` are shared. Edit in place, do not fork.

## Working style

- Plan before touching more than one file. The routing, the legs, and the fuser are coupled; a change to one often needs the others.
- After a change, run `python3 -c "import ast; ast.parse(...)"` on edited `.py` files. Run `uv run smoke-supervisor` only when credentials are available; otherwise reason from the code.
- Keep docstrings explaining why, not what. Keep workshop prose plain.

## Layout

- `agent_server/agent.py` LangGraph supervisor as an MLflow `ResponsesAgent`.
- `agent_server/supervisor.py` route, call legs, fuse, personas, audit write back.
- `agent_server/subagents/` the three domain legs and their `*_space.md` files.
- `agent_server/action_plane/` state machine, guardrails, executor, six connectors.
- `agent_server/mcp_config.py` the full MCP fleet wiring.
- `action-center/`, `e2e-chatbot-app/` the two frontend apps (TypeScript).
- `agent_evaluation_advanced.ipynb` monitoring, lineage, regression gate.
- `scripts/` setup-lakebase, seed-policies, smoke-supervisor.

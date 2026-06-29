# Modify the Supervisor

Customize the Multi-domain Supervisor: its routing, domain sub-agents, LLM, tools, and the Action Plane.

## Key Files

| File | Purpose |
|---|---|
| `agent_server/agent.py` | The LangGraph supervisor and its two tools (`ask_supervisor`, `propose_action`), the system prompt |
| `agent_server/supervisor.py` | The route, call legs, fuse core, plus personas and the audit write back |
| `agent_server/subagents/*.py` | The three domain sub-agents (Finance, SCM, Commercial) and their routing descriptions |
| `agent_server/subagents/*_space.md` | The Genie space instructions each domain leg uses as the text to SQL fallback |
| `agent_server/utils.py` | Workspace portable config (catalog, schemas, LLM endpoint, Genie space ids) |
| `agent_server/action_plane/` | The state machine, guardrails, executor, and connectors |
| `scripts/seed_action_policies.py` | The guardrail limits per action type |

## Common Modifications

### Re-route a question to a different domain

Edit the `ROUTING_DESCRIPTION` line in `agent_server/subagents/finance.py`, `scm.py`, or `commercial.py`. This single line is what the router LLM reads to decide whether a domain is needed. It is exactly the sub-agent description field of a native Agent Bricks Multi-Agent Supervisor. Edit it, then `uv run smoke-supervisor` to see the routing change.

### Add a fourth domain

1. Copy `subagents/scm.py` to `subagents/<domain>.py`. Set `DOMAIN`, `ROUTING_DESCRIPTION`, and `REFRAME_HINT`.
2. Drop a `<domain>_space.md` next to it (the Genie space instructions, using `${AKZO_CATALOG}` for the catalog).
3. Register it in `subagents/__init__.py` `REGISTRY`.
4. Add a `<DOMAIN>_SPACE_ID` env var to `.env.example` and `app.yaml`.

### Change the LLM

Set `LLM_ENDPOINT` in `.env` / `app.yaml`. Never hardcode an endpoint in code; `utils.get_llm_endpoint()` resolves it.

### Edit the supervisor's behavior

The `SYSTEM_PROMPT` in `agent_server/agent.py` defines how the supervisor decides to call its tools and how it grounds answers. The router and fuser prompts in `agent_server/supervisor.py` (`_build_router_prompt`, `fuse`) control routing and fusion.

### Tune the action ladder

Edit `scripts/seed_action_policies.py` to change a discount cap, spend cap, allowed regions, or whether an action type requires approval, then `uv run seed-policies`. The guardrail engine (`action_plane/guardrails.py`) reads these before any action executes.

### Add a connector

See the hackathon kit `add-connector` skill, or: add `action_plane/connectors/<name>.py` with `send(payload)`, register it in `connectors/__init__.py` `SYSTEMS`, add a route in `executor.py` `ROUTING`, and seed a policy.

## Testing Changes

```bash
uv run smoke-supervisor        # routing + fusion across the three domains
uvicorn agent_server.main:app --port 8000   # the REST host; curl /api/ask and /api/act
```

Run `python3 -c "import ast; ast.parse(open('agent_server/agent.py').read())"` on any file you change. Routing, legs, and the fuser are coupled, so re-run the smoke test after a routing change.

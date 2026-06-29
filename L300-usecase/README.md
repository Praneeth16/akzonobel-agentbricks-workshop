# L300: Use case, the Multi-domain Supervisor for AkzoNobel

The flagship. One governed chat surface that answers cross-functional questions about AkzoNobel's coatings business by routing each question to the right domain, consulting that domain's Genie space, and fusing one grounded answer. It is the top of all three spines at once: it composes the Agent Bricks types, wires the full MCP fleet, and takes real actions behind an approval ladder with a complete audit trail.

---

## What You Will Build

| Capability | Powered By |
|---|---|
| One answer across Finance, Supply Chain, and Commercial | LangGraph supervisor that routes, calls domain legs, and fuses |
| Three governed domain sub-agents | One Genie space each, the reused L200 finance copilot as the Finance leg |
| Row level governance per domain and persona | OBO reads under the caller's identity, so Unity Catalog row filters apply |
| Every connector, behind an approval ladder | The Action Plane: CRM, email, ERP PO, SharePoint, Teams, ServiceNow |
| L1 to L4 autonomy, escalation, and audit | Guardrail engine plus the `action_events` lineage table |
| A human in the loop approval queue | The Action Center app: ladder meter, guardrail chips, timeline |
| An end to end governed chat app | The ported Next.js app, pointed at the supervisor, with citations and tool calls |
| Production monitoring, lineage, and a regression gate | MLflow judges on live traffic, Unity Catalog lineage, a promotion gate |

---

## The Three Spines (and where L300 sits)

L300 is the deepest rung of each spine. By here you operate an agent the way you would in production.

| Spine | L300 (here) |
|---|---|
| Agent Bricks types | The supervisor composes them: three Genie spaces plus the reused finance copilot, fused into one answer |
| MCP | The full fleet. One Genie MCP server per domain, the system AI functions, and optional document tools |
| Agents that act | All connectors, the L1 to L4 approval ladder, escalation on a guardrail breach, and a full audit trail |
| LLMOps | Production monitoring with dev parity judges, Unity Catalog lineage, and a regression gate that blocks promotion |

---

## How It Works

A question enters the supervisor. The **router** (one LLM call) reads each sub-agent's one line description and decides which domains are needed, writing a domain framed subquestion for each so a domain never declines a question phrased in another domain's terms. Each chosen domain **leg** runs its governed query, the real Genie space under the caller's identity when its space id is set, or an instruction driven text to SQL fallback over the bundled space file. The **fuser** (one LLM call) takes the legs' structured rows, not free text, and produces one grounded answer plus one recommended action. If the user wants to act on the finding, the supervisor proposes an action through the Action Plane, which never executes on its own.

```
question ─▶ router ─▶ [FINANCE leg] [SCM leg] [COMMERCIAL leg] ─▶ fuser ─▶ one answer + recommended action
                          │              │             │                         │
                       Genie space    Genie space   Genie space            propose_action ─▶ Action Plane (L1-L4)
                       (OBO reads, UC row filters per persona)                                   │
                                                                                          Action Center (approve / execute)
```

The per domain description lines in `agent_server/subagents/*.py` are exactly the sub-agent description fields you fill in when you register a native Agent Bricks Multi-Agent Supervisor. Editing a line re-routes. The supervisor here is a faithful, self contained reproduction of that product, so you can read every step and later swap in the native endpoint.

---

## Get Started

The shared data setup in the repo root `data/` folder must run once before this tier. It loads the coatings tables for all three domains, the documents, the Genie spaces, and the vector index.

1. Copy `.env.example` to `.env` and set your lab's values. Locally the catalog is optional — it defaults to `current_catalog()`. Set the LLM endpoint, the warehouse, the three Genie space ids if you have them, and the Lakebase instance.
2. `uv run setup-lakebase` then `uv run seed-policies` to create the audit and Action Plane tables and load the guardrail policies for the ladder.
3. `uv run smoke-supervisor` to see routing and fusion across all three domains.
4. `uv run start-server` to serve the supervisor over the Responses API, or `uvicorn agent_server.main:app --port 8000` for the simple REST host.
5. Open `action-center/` to run the approval queue, and `e2e-chatbot-app/` for the full governed chat surface pointed at the supervisor.
6. Work through `agent_evaluation_advanced.ipynb` for production monitoring, lineage, and the regression gate.

Nothing is hardcoded to a workspace. The catalog, schemas, LLM endpoint, warehouse, Genie space ids, and Lakebase instance all come from the environment, so the same code runs identically on a lab such as Vocareum or your own workspace.

---

## Deploy to Databricks Apps

The app is deployed with the bundle in `databricks.yml`. Every workspace value is a bundle variable, so nothing is hardcoded — you supply them at deploy time:

```bash
databricks bundle deploy \
  --var catalog=<your_catalog> \
  --var llm_endpoint=<your_chat_serving_endpoint> \
  --var warehouse_id=<your_warehouse_id> \
  --var finance_space_id=<...> --var scm_space_id=<...> --var commercial_space_id=<...> \
  --var lakebase_instance=<your_lakebase_instance> \
  --var experiment_id=<your_mlflow_experiment_id>
```

`catalog` is **required for Apps**. The Apps runtime has no Spark session, so `current_catalog()` cannot resolve there; `AKZO_CATALOG` is set from `${var.catalog}` in the app's `config.env`. (Locally, `current_catalog()` still works, so the `.env` catalog stays optional.)

After deploying, grant the app's service principal the access it needs to read the three domain schemas and run the governed action path:

```bash
uv run grant-app-access --sp <app-service-principal> --catalog <your_catalog>
```

This grants the SP `USE CATALOG` / `USE SCHEMA` / `SELECT` on the finance, SCM, and commercial schemas, `EXECUTE` on the `akzo_external_systems` UC connection, and `CAN RUN` on each domain's Genie space (read from the `*_SPACE_ID` env; pass `--skip-genie` to skip). The SP and the catalog are parameters — neither is hardcoded. The SP also needs `CAN_USE` on the warehouse and access to the Lakebase instance, which you grant from the workspace UI.

---

## Prerequisites

- Databricks workspace with serverless SQL compute and Unity Catalog
- Foundation Model API access (for example Claude Sonnet)
- Three Genie spaces, one per domain (Finance, Supply Chain, Commercial), or the text to SQL fallback over the bundled space files
- Lakebase enabled (for the audit trail and the Action Plane tables)
- Databricks Apps enabled (for the Action Center and the chat app)
- Shared data setup completed (see `../data/`)

---

## Folder Contents

| Path | Purpose |
|------|---------|
| `agent_server/agent.py` | The LangGraph supervisor, wrapped as an MLflow `ResponsesAgent` |
| `agent_server/supervisor.py` | The route, call legs, fuse core, with personas and the audit write back |
| `agent_server/subagents/` | The three domain sub-agents (Finance reused from L200, plus SCM and Commercial) and their Genie space files |
| `agent_server/action_plane/` | The Action Plane: state machine, guardrail engine, executor, and all six connectors |
| `agent_server/actions_api.py` | The Act, Approve, Execute REST loop mounted by the app |
| `agent_server/mcp_config.py` | The full MCP fleet wiring (one Genie server per domain, system AI, optional docs) |
| `agent_server/main.py`, `start_server.py` | The FastAPI REST host and the MLflow Responses server entry points |
| `action-center/` | The human in the loop approval queue app (ladder meter, guardrail chips, timeline) |
| `e2e-chatbot-app/` | The end to end governed chat app, pointed at the supervisor |
| `agent_evaluation_advanced.ipynb` | Production monitoring, Unity Catalog lineage, and the regression gate |
| `scripts/` | `setup-lakebase`, `seed-policies`, `smoke-supervisor`, `grant-app-access` (grant the app SP UC + Genie access) |
| `docs/` | Architecture notes and the tier diagram |

---

## The Action Ladder (L1 to L4)

Every action flows through one governed plane and one state machine. The `level` on an action is its autonomy tier, and the guardrail engine decides what each tier may do.

| Level | Meaning | Behavior |
|---|---|---|
| L1 | Propose only | The agent stages the action; a human always approves |
| L2 | Propose with a recommendation | Default. The agent advises; a human approves and executes |
| L3 | Execute on approval | Once approved, the agent runs the connectors and records the external ref |
| L4 | Auto approve within policy | The action auto approves only when it is within policy and does not require approval; any guardrail breach escalates back to a human gate |

`proposed → approved → executing → executed`, with `rejected`, `failed`, and `escalated` as the off ramps. Every transition and its audit event are written in one atomic transaction, so an action can never end up approved or executed without its `action_events` row. The ladder decision (`action_plane.decide`) is enforced when you act: a guardrail breach escalates at propose and at approve time, an L4 within policy action auto approves and executes, and L1 to L3 always wait for a human. See `agent_server/action_plane/model.py` and `agent_server/action_plane/guardrails.py`. Run `uv run test-action-ladder` (or `python3 scripts/test_action_ladder.py`) to verify the ladder and the atomicity guarantee offline, with no workspace.

The supervisor itself routes only Finance, Supply Chain, and Commercial questions. Anything outside those three domains is declined gracefully without querying any Genie space.

---

## Next

This is the top of the ladder. Move to `../hackathon-starter-kit/` to fork these patterns into your own use case: scaffold a copilot, add a connector with guardrails, add a Genie space, and add an MCP tool.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.

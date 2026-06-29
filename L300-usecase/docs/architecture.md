# L300 Architecture: the Multi-domain Supervisor

This note describes the runtime shape of the flagship tier. A rendered diagram belongs at
`docs/architecture.png` (export from the tier's draw.io source when available); until then,
the ASCII sketch in the top level `README.md` and the description here are the reference.

## Components

```
                          ┌──────────────────────────────────────────────┐
   user / chat app  ─────▶│  agent_server/agent.py  (LangGraph supervisor) │
   (e2e-chatbot-app)      │  MLflow ResponsesAgent · tools:                │
                          │    ask_supervisor   propose_action            │
                          └───────────┬───────────────────┬──────────────┘
                                      │                   │
                    ┌─────────────────▼──────────┐   ┌────▼───────────────────────┐
                    │ supervisor.py              │   │ action_plane/              │
                    │  route → legs → fuse       │   │  state machine + guardrails│
                    └───────┬────────────────────┘   │  + 6 connectors            │
                            │                         └────┬───────────────────────┘
        ┌───────────────────┼───────────────────┐         │
        ▼                   ▼                   ▼          ▼
  subagents/finance   subagents/scm   subagents/commercial    Action Center app
   Genie space         Genie space      Genie space            (approve / execute,
   (OBO reads)         (OBO reads)      (OBO reads)             L1-L4 ladder, audit)
        └───────── governed SQL on the serverless warehouse ──────────┘
                            │
                   Unity Catalog (row filters per persona)

   Lakebase (akzo schema): agent_sessions · agent_feedback · actions · action_events · action_policies
```

## The read plane

`ask_supervisor` calls `supervisor.supervise()`. The router (one LLM call) reads each
sub-agent's `ROUTING_DESCRIPTION` and picks domains plus domain framed subquestions. Each
leg runs the real Genie space under the caller's identity (OBO) when its `<DOMAIN>_SPACE_ID`
is set, else the `text2sql` fallback over the bundled `*_space.md`. The fuser (one LLM call)
turns the legs' rows into one grounded answer plus a recommended action. The turn is logged
to `agent_sessions`.

Row level governance is per domain: because the leg's SQL runs under the signed in user,
Unity Catalog row filters narrow what each persona (controller, EMEA planner, account rep)
sees. The persona scope is recorded on the trace.

## The act plane

`propose_action` stages an action through the Action Plane in status `proposed`. It never
executes. The guardrail engine checks discount/spend caps, allowed regions, and the
approval requirement. A human approves and executes in the Action Center; the executor
dispatches to the connectors (email, CRM, ERP PO, SharePoint, Teams, ServiceNow) through a
governed HTTP path (a Unity Catalog connection, with an SP direct fallback). The `level`
(L1 to L4) sets autonomy; an L4 within policy action may auto approve, while any breach
escalates back to a human gate. Every transition appends an `action_events` row.

## The MCP fleet

`mcp_config.py` enumerates the managed MCP servers: one Genie server per domain, the system
AI functions server, and an optional vector search server for document tools. The read plane
calls Genie via the Conversation API directly (to capture SQL + rows for the trace); the MCP
fleet is the alternative native wiring that exposes each Genie space as a first class tool.

## LLMOps

`agent_evaluation_advanced.ipynb` runs offline evaluation with an MLflow judge suite and a
routing scorer, registers production monitors that score live traffic with the same judges,
reads Unity Catalog lineage across the three domain schemas and the audit tables, and runs a
regression gate that blocks promotion on a score drop.

## Portability

Nothing is hardcoded to a workspace. `agent_server/utils.py` resolves the catalog
(`AKZO_CATALOG` env → `current_catalog()` → `main`), schemas, LLM endpoint, warehouse, Genie
space ids, and Lakebase instance from the environment, so the tier runs unchanged on a lab
such as Vocareum or your own workspace.

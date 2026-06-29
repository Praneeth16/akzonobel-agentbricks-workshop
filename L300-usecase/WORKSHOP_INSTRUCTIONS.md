# L300 Workshop Instructions: the Multi-domain Supervisor

A step by step path through the flagship tier. Allow about 90 minutes. You will stand up the supervisor, watch it route across three domains, approve an action through the ladder, run the chat app, and operate the production monitoring.

Before you start, run the shared data setup in the repo root `data/` folder once. It loads all three domain schemas, the Genie spaces, and the vector index.

---

## Step 1. Configure your lab (10 min)

1. Copy the environment template: `cp .env.example .env`.
2. Set the values for your workspace. You can leave `AKZO_CATALOG` blank to use `current_catalog()`.
   - `DATABRICKS_WAREHOUSE_ID` for the governed text to SQL fallback legs.
   - `FINANCE_SPACE_ID`, `SCM_SPACE_ID`, `COMMERCIAL_SPACE_ID` if you created the three Genie spaces. Leave blank to use the bundled space files as the fallback.
   - `LAKEBASE_INSTANCE` for the audit trail and the Action Plane tables.
3. Confirm auth: set `DATABRICKS_CONFIG_PROFILE` to a working CLI profile, or `DATABRICKS_HOST` plus `DATABRICKS_TOKEN`.

Nothing is hardcoded. If a value is unset, the code either resolves a sensible default or degrades gracefully (for example, a domain without a Genie space id uses the text to SQL fallback).

---

## Step 2. Create the tables (5 min)

```bash
uv run setup-lakebase   # creates agent_sessions, agent_feedback, actions, action_events, action_policies
uv run seed-policies    # loads the guardrail limits per action type for the L1 to L4 ladder
```

The audit and Action Plane tables live in the `akzo` schema on your Lakebase instance.

---

## Step 3. Watch the supervisor route and fuse (15 min)

```bash
uv run smoke-supervisor
```

You will see four questions run:
- A margin question routes to **Finance**.
- An OTIF question routes to **Supply Chain**.
- A churn question routes to **Commercial**.
- A cross domain why question routes to **several** and the answer connects them.

For each, the output prints the routed domains, the path each leg used (`genie_space` or the `ai_query` fallback), the row counts, and the fused answer plus one recommended action. An out of scope question is declined rather than answered wrongly.

Open `agent_server/subagents/finance.py`, `scm.py`, and `commercial.py`. The `ROUTING_DESCRIPTION` line in each is what the router reads. Edit one and re-run the smoke test to see the routing change. These lines are the sub-agent description fields of a native Agent Bricks Multi-Agent Supervisor.

---

## Step 4. Serve the supervisor (10 min)

```bash
uvicorn agent_server.main:app --reload --port 8000
```

Then ask it a question:

```bash
curl -s localhost:8000/api/ask -H 'content-type: application/json' \
  -d '{"question": "Why did Paints EMEA margin fall in Q2 2026?", "persona": "controller"}' | python3 -m json.tool
```

Notice the `persona_scope` in the response. Change `persona` to `emea_planner` or `rep`. In a deployed app, the Genie reads run under the signed in user's identity, so Unity Catalog row filters narrow what each persona actually sees. For the Responses API serving surface used by the chat app, use `uv run start-server` instead.

---

## Step 5. Act behind the approval ladder (20 min)

The supervisor can propose an action when you ask it to act on a finding. It never executes on its own. Stage one through the Action Plane:

```bash
curl -s localhost:8000/api/act -H 'content-type: application/json' \
  -d '{"action_type": "scm_reorder", "subject": "Reorder resin for EMEA stockout",
       "region": "EMEA", "level": 2,
       "payload": {"supplier": "Acme Resins", "sku": "RES-1001", "qty": 500, "amount_eur": 120000}}' \
  | python3 -m json.tool
```

The response carries the proposed action and the **guardrail verdict** (which checks passed, which limits applied). Now run the Action Center to approve and execute it through the queue:

```bash
cd action-center && ./run_local.sh
```

The Action Center shows the L1 to L4 ladder meter, the guardrail chips, the timeline, and the full `action_events` audit. Try:
- An L2 action: it waits for your approval, then executes.
- An action that breaches a guardrail (for example a `scm_reorder` over the spend cap): it escalates back to a human gate rather than executing.
- Remember separation of duties. The proposer (the agent) cannot also approve.

---

## Step 6. The end to end chat app (10 min)

```bash
cd e2e-chatbot-app
# set .env to point DATABRICKS_SERVING_ENDPOINT at the supervisor (or API_PROXY at the local server)
```

The chat app holds a multi turn, cross domain conversation and surfaces the citations and tool calls. An action proposing turn renders the approval prompt rather than executing silently. See the app's own README for the run steps.

---

## Step 7. Operate it like production (10 min)

Open `agent_evaluation_advanced.ipynb`. Set the widgets, then run top to bottom. You will:
- Score the supervisor over a cross domain eval set with an MLflow judge suite plus a routing scorer.
- Register production monitors that score live traffic with the same judges.
- Read the Unity Catalog lineage across the three domain schemas and the audit tables.
- Run the regression gate, which fails the cell if a candidate drops below the production baseline.

---

## You are done

You operated a governed, multi-domain production agent: it routes across Finance, Supply Chain, and Commercial, returns one grounded answer, acts only behind an approval ladder with a full audit trail, and is monitored with a regression gate. To build your own, fork the patterns in `../hackathon-starter-kit/`.

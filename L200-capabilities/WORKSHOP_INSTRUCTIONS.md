# L200 Lab Guide: a coded agent that uses tools and acts

This is the hands on path through L200. Each step has a clear "you should see" checkpoint. Allow about 90 minutes. All data is synthetic.

> Prerequisite: the shared data setup in `../data/` has been run, so the `akzo_finance`, `akzo_scm`, and `akzo_commercial` schemas and the UC function tools exist in your catalog.

---

## Step 0. Configure the environment

```bash
cd L200-capabilities
cp .env.example .env
```

Edit `.env` and set, at minimum:

```bash
AKZO_CATALOG=<your-catalog>      # on Vocareum, your assigned catalog
LLM_ENDPOINT=databricks-claude-sonnet-4-5
```

Then install dependencies:

```bash
uv sync
```

**Checkpoint:** `uv run discover-tools --catalog $AKZO_CATALOG --schema akzo_tools` lists the UC functions in your tools schema.

---

## Step 1. Run the agent locally and call a tool

```bash
uv run start-app
```

In another terminal:

```bash
curl -X POST http://localhost:8000/invocations \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"Which region had the lowest gross margin last quarter?"}]}'
```

**Checkpoint:** the agent answers with a figure drawn from your finance data, and the MLflow trace shows a UC function MCP tool call. If `AKZO_CATALOG` is unset, the agent starts with no tools and says so.

---

## Step 2. Build and register the MCP server

The agent already exposes every function in `AKZO_CATALOG.AKZO_TOOLS_SCHEMA` through the managed UC functions MCP server. To register your own functions as tools, create a SQL UDF in that schema, then re-run discovery.

```sql
CREATE OR REPLACE FUNCTION ${AKZO_CATALOG}.akzo_tools.top_supplier_otif()
RETURNS TABLE(supplier STRING, otif_pct DOUBLE)
RETURN SELECT supplier, otif_pct FROM ${AKZO_CATALOG}.akzo_scm.supplier_otif ORDER BY otif_pct ASC LIMIT 1;
```

**Checkpoint:** `discover-tools` now lists `top_supplier_otif`, and asking the agent "what is the OTIF of our weakest supplier" calls it. See the **add-tools** skill to grant the function to the deployed app.

---

## Step 3. Add memory

Run `scripts/lakebase_setup_script.ipynb` with your Lakebase instance name, then set in `.env`:

```bash
LAKEBASE_INSTANCE_NAME=<your-instance>
```

Restart the agent and hold a two turn conversation with the same `session_id` (see the **agent-memory** skill).

**Checkpoint:** the second turn recalls a fact stated in the first.

---

## Step 4. Turn on the Action Plane

```bash
export LAKEBASE_INSTANCE=<your-instance>
uv run python scripts/actions_schema_setup.py     # creates tables, seeds L200 policies
```

Set `ENABLE_ACTIONS_API=true` in `.env` and restart. Now propose, approve, and execute an action:

```bash
# 1. Propose — lands in status 'proposed'
curl -X POST http://localhost:8000/api/act \
  -H "Content-Type: application/json" \
  -d '{"action_type":"email_notify","subject":"Margin alert","payload":{"to":"controller@akzonobel.com","body":"EMEA margin down 3 points."},"region":"EMEA"}'

# 2. Approve (use the returned action id)
curl -X POST http://localhost:8000/api/actions/1/approve

# 3. Execute — runs the email connector
curl -X POST http://localhost:8000/api/actions/1/execute
```

**Checkpoints:**
- After step 1 the action status is `proposed` and the guardrail verdict is returned.
- The action **cannot** execute before it is approved (try executing first — you get a 409).
- An action whose `region` is outside the policy's `allowed_regions`, or whose spend exceeds the cap, escalates instead of executing.
- `GET /api/actions/1` shows the full event lineage: proposed, approved, executing, executed.

> The connectors call a mock external systems app through a Unity Catalog HTTP connection. If you do not have one set up, the propose and approve steps still work and demonstrate the governance gate; execute needs `AKZO_MOCK_SYSTEMS_URL` or the UC connection.

---

## Step 5. Run the characterization tests

These run with no Databricks connection, so they are a good first thing to run.

```bash
uv run pytest tests
```

**Checkpoint:** the state machine and guardrail tests pass. They lock in the behavior of the ported `evaluate()` and the seven state machine before you change connectors.

---

## Step 6. Evaluate with the judge suite

Open `agent_evaluation.ipynb`, set the `llm_endpoint` and `catalog` widgets, and run it.

**Checkpoint:** an MLflow run shows per row Correctness and Groundedness (plus relevance and safety), each with a rationale, and an aggregate pass rate. If you configured AI Gateway, the agent's model calls are logged to the `akzo_llmops` inference tables.

---

## Step 7. Deploy

Follow the **deploy** skill:

```bash
uv run preflight
databricks bundle validate
databricks bundle deploy --var="catalog=$AKZO_CATALOG" --var="lakebase_instance=<your-instance>"
databricks bundle run akzo_capabilities_agent
```

Then grant the app's service principal access to Lakebase (the **lakebase-setup** skill).

**Checkpoint:** the deployed app answers a query, and a query that needs recalled memory returns the right answer.

---

## What you learned

- A coded agent calls Unity Catalog function tools through an MCP server.
- Memory on Lakebase carries context across turns.
- The Action Plane makes "agents that act" safe: every action is proposed, evaluated against guardrails, and held until a human approves.
- A judge suite and AI Gateway are the L200 LLMOps and governance layer.

Move up to `../L300-usecase/`.

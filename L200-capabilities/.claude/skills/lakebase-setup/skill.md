---
name: lakebase-setup
description: "Set up Lakebase (managed Postgres) for the L200 agent: short-term memory + the Action Plane tables, and grant the app's service principal access after deploy. Use when: (1) Enabling memory or actions, (2) 'lakebase' / 'postgres' / 'database instance' errors, (3) User says 'set up memory', 'set up actions', or 'grant lakebase'."
---

# Lakebase Setup

Lakebase backs two things at L200: **short-term memory** (`agent_openai_memory` schema) and the **Action Plane** (`akzo_actions` schema). Nothing is hardcoded — you provide the instance name.

## 1. Point at your instance

Set ONE memory connection and the actions instance in `.env`:

```bash
# Memory (set ONE of these):
LAKEBASE_INSTANCE_NAME=<your-instance>        # provisioned
# LAKEBASE_AUTOSCALING_ENDPOINT=projects/<p>/branches/<b>/endpoints/primary
LAKEBASE_AGENT_MEMORY_SCHEMA=agent_openai_memory

# Action Plane:
LAKEBASE_INSTANCE=<your-instance>
LAKEBASE_SCHEMA=akzo_actions
```

> On a Vocareum lab, `<your-instance>` is the Lakebase instance assigned to your lab. Never hardcode someone else's instance.

## 2. Create the schemas + Action Plane tables

Run the setup notebook `scripts/lakebase_setup_script.ipynb` (it creates both schemas), then create the Action Plane tables and seed the L200 policies:

```bash
uv run python scripts/actions_schema_setup.py
```

This creates `actions`, `action_events`, `action_policies` and seeds four policies (`email_notify`, `quote_send`, `escalation`, `ticket_open`) — all with `requires_approval = true`, so nothing executes without a human approval. The agent server creates the memory tables itself on first start.

## 3. After deploy: grant the app's service principal

```bash
# Get the deployed app's SP client id
SP=$(databricks apps get agent-akzo-capabilities --output json | jq -r '.service_principal_client_id')

# Grant memory schema access (openai memory type)
uv run python scripts/grant_lakebase_permissions.py "$SP" --memory-type openai --instance-name <your-instance>
```

The Action Plane schema (`akzo_actions`) needs the same SP granted USAGE/CREATE on the schema and SELECT/INSERT/UPDATE on its tables; the script grants the configured `LAKEBASE_AGENT_MEMORY_SCHEMA` plus shared schemas — add `akzo_actions` to its grant list if your tables live there.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `LAKEBASE_INSTANCE is not set` | Set it in `.env` (Action Plane path). |
| `database instance ... not found` | The instance name is wrong or you lack access. |
| Grants fail "does not exist yet" | Expected on a fresh branch — re-run after first agent use. |
| 503 "Lakebase unavailable" from the agent | Memory schema or grant missing; re-run steps 2–3. |

---
name: deploy
description: "Deploy the L200 agent to Databricks Apps with Databricks Asset Bundles. Use when: (1) User says 'deploy', 'push to databricks', or 'bundle deploy', (2) 'App already exists' error, (3) Binding an existing app, (4) Querying or debugging the deployed app."
---

# Deploy to Databricks Apps

> **Auth:** On Vocareum you run inside the workspace; CLI commands need no profile. Locally, read `DATABRICKS_CONFIG_PROFILE` from `.env` and pass `--profile <profile>`.

The bundle resource key is `akzo_capabilities_agent` and the app name is `agent-akzo-capabilities` (prefix `agent-`). Nothing in `databricks.yml` is tied to one workspace — catalog, warehouse, endpoint, and Lakebase instance are bundle **variables** you pass at deploy.

## Deploy

```bash
# 1. Pre-flight: start locally, send a test request, verify a response
uv run preflight

# 2. Validate
databricks bundle validate

# 3. Deploy (pass per-workspace values as vars)
databricks bundle deploy \
  --var="catalog=<your-catalog>" \
  --var="llm_endpoint=databricks-claude-sonnet-4-5" \
  --var="lakebase_instance=<your-instance>" \
  --var="experiment_id=<your-experiment-id>"

# 4. Run (REQUIRED — deploy only uploads; run starts the new code)
databricks bundle run akzo_capabilities_agent
```

## "App already exists"

Bind the existing app instead of recreating it:

```bash
databricks bundle deployment bind akzo_capabilities_agent <existing-app-name> --auto-approve
databricks bundle deploy
```

If binding fails with "already managed by Terraform", it is already bound — just deploy.

## Query the deployed app

Databricks Apps accept **OAuth tokens only** (a PAT gives a 302 redirect):

```bash
TOKEN=$(databricks auth token | jq -r '.access_token')
APP_URL=$(databricks apps get agent-akzo-capabilities --output json | jq -r '.url')

curl -X POST "$APP_URL/invocations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input":[{"role":"user","content":"hi"}]}'
```

## After deploy

- Grant the app's SP access to Lakebase — see **lakebase-setup**.
- If you enabled the Action Plane, set `ENABLE_ACTIONS_API=true` in `databricks.yml` config env and re-deploy.

## Debug

```bash
databricks apps logs agent-akzo-capabilities --follow
databricks apps get agent-akzo-capabilities --output json | jq '{app_status, compute_status}'
```

| Issue | Fix |
|-------|-----|
| 302 redirect | Use an OAuth token, not a PAT. |
| App runs old code | Run `databricks bundle run akzo_capabilities_agent` after deploy. |
| Env var is None in app | Check `value` / `value_from` in `databricks.yml` config env. |
| Lakebase 503 | See **lakebase-setup** (schema + SP grant). |

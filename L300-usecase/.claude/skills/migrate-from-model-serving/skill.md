# Migrate the Supervisor from Model Serving to Databricks Apps

Guide for moving the Multi-domain Supervisor from a Model Serving endpoint to a Databricks App. The supervisor is already wrapped as an MLflow `ResponsesAgent` (`agent_server/agent.py`), so most of the work is wiring resources and auth, not rewriting the agent.

> This is a starting stub. Fill in your workspace specifics as you migrate; the steps below are the path.

## Key Differences

| Aspect | Model Serving | Databricks Apps |
|---|---|---|
| Interface | ChatCompletions API | Responses API (the supervisor already uses this) |
| Auth | PAT or OAuth | OAuth, with OBO token forwarding for per user Genie reads |
| UI | Separate deployment | The `e2e-chatbot-app/` chat surface, or the Action Center |
| Resources | Serving endpoint config | App resources plus the service principal |
| Framework | MLflow pyfunc | MLflow `AgentServer` (`agent_server/start_server.py`) |

## Migration Steps

### 1. The agent interface is already Apps ready

`agent_server/agent.py` exposes `AkzoSupervisorAgent(ResponsesAgent)` and `start_server.py` serves it with `AgentServer`. No interface rewrite is needed. Confirm `mlflow.models.set_model(AGENT)` is the models from code entry point.

### 2. Move config from endpoint env to app resources

In Model Serving you set the warehouse, Genie space ids, and Lakebase via the endpoint config. In Apps, wire them as app resources and `valueFrom` env in `app.yaml` (or the bundle variables in `databricks.yml`):
- The three Genie spaces as `genie_space` resources, mapped to `FINANCE_SPACE_ID` / `SCM_SPACE_ID` / `COMMERCIAL_SPACE_ID`.
- The SQL warehouse, mapped to `DATABRICKS_WAREHOUSE_ID`.
- Lakebase as a `postgres` resource, mapped to `LAKEBASE_INSTANCE`.
- The MLflow experiment as an `experiment` resource.

Keep everything env driven; never hardcode a value (see `agent_server/utils.py`).

### 3. Switch auth to OBO

The supervisor's Genie legs read under the caller's identity when the app forwards the user's token. The `main.py` and `actions_api.py` already read `X-Forwarded-Access-Token` and the `X-Forwarded-Email` identity headers. Grant the app's service principal the fallback permissions, and confirm the Genie spaces honor row filters under OBO.

### 4. Grant Lakebase to the app identity

The app service principal needs `CAN_CONNECT_AND_CREATE` on the Lakebase instance for the audit and Action Plane tables. Run `uv run setup-lakebase` and `uv run seed-policies` once against the instance.

### 5. Deploy and verify

Deploy with the bundle (`databricks bundle deploy`) or the Apps UI. Verify with the L300 workshop instructions: ask a cross domain question, propose an action, and approve it in the Action Center.

## Pitfalls

- Do not mix a forwarded user token with the app SP OAuth in one client. The supervisor uses `auth_type='pat'` for the OBO client to avoid the "more than one authorization method" error (see `supervisor._user_genie_client`).
- A missing Genie space id falls back to text to SQL; make sure the warehouse is set so the fallback works.
- Audit writes are best effort; a missing Lakebase will not sink an answer, but it will lose the trace. Set `LAKEBASE_INSTANCE`.

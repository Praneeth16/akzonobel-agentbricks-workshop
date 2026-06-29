# Action Plane — agents that act, behind a human gate

The Action Plane is the one governed plane every AkzoNobel agent acts through. An agent never calls an external system directly. It **proposes** an action; the action is checked against guardrails; a human **approves** it; only then does the executor run the connector. Every transition is recorded in `action_events`, so who did what, when, and why is always reconstructable.

This is the L200 slice: only the **email** and **ticket** connectors are enabled, and every policy has `requires_approval = true`. L300 adds the rest of the connectors and the L1 to L4 autonomy ladder.

## The state machine

```
proposed ──approve──▶ approved ──mark_executing──▶ executing ──mark_executed──▶ executed
   │                     │                            │
   ├──reject──▶ rejected │                            └──mark_failed──▶ failed
   │                     │
   └──escalate─┐         └──escalate──▶ escalated
               ▼
           escalated   (reachable from any non-terminal state on a guardrail breach)
```

Illegal transitions raise. A compare-and-set guard on every UPDATE prevents a double-execute when two approvals race. Each transition's status UPDATE and its `action_events` audit row are written in **one transaction** (`lakebase.transaction()`), so a status can never advance without its matching audit event — if the event write fails, the whole transition rolls back. Separation of duties (the proposer may not approve or reject their own action) is enforced inside `ActionPlane.approve()` / `reject()`, with the HTTP route keeping its own check as defense in depth.

## The pieces

| File | Role |
|------|------|
| `model.py` | `ActionPlane` — the state machine over the Lakebase `actions` + `action_events` tables |
| `guardrails.py` | `evaluate(action)` — checks the action against its row in `action_policies` (action type allowed, discount cap, spend cap, region scope, requires_approval) and returns a structured verdict. It never mutates |
| `executor.py` | `execute(action_id)` — re-runs guardrails as a final gate, then dispatches an approved action to its connector(s) and drives the machine to `executed` / `failed` / `escalated` |
| `connectors/email.py`, `connectors/ticket.py` | The two enabled connectors. Each `send(payload)` POSTs through a governed path |
| `connectors/_http.py` | Governed transport: a UC HTTP connection first, an SP-direct HTTPS POST as fallback |
| `lakebase.py` | Short-lived-credential Postgres access (the write governance plane) |
| `databricks_client.py` | SQL warehouse + SDK helper used by the connectors |

## Setup

1. Configure Lakebase (see the **lakebase-setup** skill): set `LAKEBASE_INSTANCE` and `LAKEBASE_SCHEMA`.
2. Create the tables and seed the L200 policies:
   ```bash
   uv run python ../scripts/actions_schema_setup.py
   ```
3. Set `ENABLE_ACTIONS_API=true` so the HTTP routes mount on the agent server.
4. For real connector execution, set `AKZO_MOCK_SYSTEMS_URL` (or stand up the `akzo_external_systems` UC HTTP connection). Without it, propose/approve still work and demonstrate the governance gate.

## The L200 action types

Seeded by `scripts/actions_schema_setup.py`, all with `requires_approval = true`:

| action_type | Connector | Guardrails |
|---|---|---|
| `email_notify` | email | region must be in EMEA/NA/APAC/LATAM |
| `quote_send` | email | discount ≤ 15%, spend ≤ EUR 50,000, region in EMEA/NA |
| `escalation` | ticket | always requires approval |
| `ticket_open` | ticket | always requires approval |

## The loop (HTTP)

```
POST /api/act                       → propose (status: proposed) + guardrail verdict
POST /api/actions/{id}/approve      → proposed|escalated → approved (separation of duties enforced)
POST /api/actions/{id}/reject       → → rejected
POST /api/actions/{id}/execute      → run connector(s) → executed | failed | escalated
GET  /api/actions[?status=]         → this agent's queue
GET  /api/actions/{id}              → one action + full event lineage + current verdict
```

## Tests

`tests/test_action_plane.py` exercises the state machine and `evaluate()` with an in-memory fake database — no Databricks needed. Run them before changing guardrails or the model:

```bash
uv run pytest tests
```

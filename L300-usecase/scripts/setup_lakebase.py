"""Create the Lakebase tables the supervisor + Action Plane write to.

Run once against your lab's Lakebase instance (set LAKEBASE_INSTANCE in .env):

    uv run setup-lakebase

Creates, in the ``akzo`` schema (idempotent — IF NOT EXISTS):
  - agent_sessions   : one row per supervisor turn (audit of routing + fused answer)
  - agent_feedback   : human thumbs up/down on a session
  - actions          : the Action Plane state machine record
  - action_events    : append-only lineage of every action transition (the audit trail)
  - action_policies  : per action_type guardrail limits (discount/spend caps, region scope)

All identifiers are static DDL — nothing is interpolated from user input.
"""
from __future__ import annotations

import sys

# Import from the agent_server package so the shared lakebase module is reused.
sys.path.insert(0, "agent_server")

import lakebase as lb  # noqa: E402

DDL = [
    # --- supervisor audit -------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS agent_sessions (
        session_id     BIGSERIAL PRIMARY KEY,
        session_uuid   UUID NOT NULL UNIQUE,
        user_email     TEXT,
        question       TEXT NOT NULL,
        routed_domains TEXT,
        fused_answer   TEXT,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_feedback (
        feedback_id  BIGSERIAL PRIMARY KEY,
        session_uuid UUID NOT NULL,
        user_email   TEXT,
        rating       INTEGER NOT NULL,
        comment      TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    # --- action plane -----------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS actions (
        id           BIGSERIAL PRIMARY KEY,
        agent        TEXT NOT NULL,
        action_type  TEXT NOT NULL,
        subject      TEXT NOT NULL,
        payload      JSONB,
        status       TEXT NOT NULL DEFAULT 'proposed',
        level        INTEGER NOT NULL DEFAULT 2,
        region       TEXT,
        requested_by TEXT,
        approved_by  TEXT,
        result       JSONB,
        external_ref TEXT,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        decided_at   TIMESTAMPTZ,
        executed_at  TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_events (
        id        BIGSERIAL PRIMARY KEY,
        action_id BIGINT NOT NULL REFERENCES actions(id),
        ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
        event     TEXT NOT NULL,
        actor     TEXT,
        detail    JSONB
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_policies (
        action_type      TEXT PRIMARY KEY,
        max_discount_pct NUMERIC,
        max_spend_eur    NUMERIC,
        allowed_regions  TEXT[],
        requires_approval BOOLEAN NOT NULL DEFAULT true
    )
    """,
]


def main() -> None:
    for stmt in DDL:
        lb.execute(stmt)
    print(f"Lakebase schema ready in '{lb.PG_SCHEMA}' on instance '{lb.INSTANCE_NAME}'.")
    print("Tables: agent_sessions, agent_feedback, actions, action_events, action_policies.")
    print("Next: `uv run seed-policies` to load the guardrail policies for the L1-L4 ladder.")


if __name__ == "__main__":
    main()

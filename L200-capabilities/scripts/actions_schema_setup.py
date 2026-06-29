"""Create the Action Plane schema + L200 policies in Lakebase.

Run once after your Lakebase instance is configured (see the lakebase-setup
skill). It creates the `actions` and `action_events` tables and an
`action_policies` table seeded with the four L200 action types — all with
`requires_approval = true`, so nothing the agent proposes can execute without a
human approval.

Everything is read from the environment (no workspace, instance, or schema is
hardcoded):

    LAKEBASE_INSTANCE   required; your Lakebase instance name
    LAKEBASE_SCHEMA     optional; default "akzo_actions"

Usage:
    uv run python scripts/actions_schema_setup.py
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Import after load_dotenv so the module-level env reads see the .env values.
from action_plane import lakebase  # noqa: E402

SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "akzo_actions")

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}",
    """
    CREATE TABLE IF NOT EXISTS actions (
        id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        agent         text        NOT NULL,
        action_type   text        NOT NULL,
        subject       text        NOT NULL,
        payload       jsonb       NOT NULL DEFAULT '{}'::jsonb,
        status        text        NOT NULL DEFAULT 'proposed',
        level         int         NOT NULL DEFAULT 2,
        region        text,
        requested_by  text,
        approved_by   text,
        external_ref  text,
        result        jsonb,
        created_at    timestamptz NOT NULL DEFAULT now(),
        decided_at    timestamptz,
        executed_at   timestamptz
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_events (
        id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        action_id  bigint      NOT NULL REFERENCES actions(id),
        ts         timestamptz NOT NULL DEFAULT now(),
        event      text        NOT NULL,
        actor      text        NOT NULL,
        detail     jsonb
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_policies (
        action_type      text PRIMARY KEY,
        max_discount_pct numeric,
        max_spend_eur    numeric,
        allowed_regions  text[],
        requires_approval boolean NOT NULL DEFAULT true
    )
    """,
]

# L200 policies: only the email + ticket action types, all requiring approval.
POLICIES = [
    # action_type, max_discount_pct, max_spend_eur, allowed_regions, requires_approval
    ("email_notify", None, None, ["EMEA", "NA", "APAC", "LATAM"], True),
    ("quote_send", 15.0, 50000.0, ["EMEA", "NA"], True),
    ("escalation", None, None, None, True),
    ("ticket_open", None, None, None, True),
]


def main() -> None:
    print(f"Creating Action Plane schema '{SCHEMA}' in Lakebase '{lakebase.INSTANCE_NAME}'...")
    for stmt in DDL:
        lakebase.execute(stmt)
    print("  Tables ready: actions, action_events, action_policies")

    for (atype, disc, spend, regions, requires) in POLICIES:
        lakebase.execute(
            "INSERT INTO action_policies "
            "(action_type, max_discount_pct, max_spend_eur, allowed_regions, requires_approval) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (action_type) DO UPDATE SET "
            "max_discount_pct = EXCLUDED.max_discount_pct, "
            "max_spend_eur = EXCLUDED.max_spend_eur, "
            "allowed_regions = EXCLUDED.allowed_regions, "
            "requires_approval = EXCLUDED.requires_approval",
            (atype, disc, spend, regions, requires),
        )
    print(f"  Seeded {len(POLICIES)} L200 policies (all requires_approval = true).")
    print("Done.")


if __name__ == "__main__":
    main()

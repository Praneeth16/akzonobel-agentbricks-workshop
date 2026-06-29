"""Seed the Action Plane guardrail policies — one row per action_type.

Run after setup-lakebase:

    uv run seed-policies

The guardrail engine (``action_plane.guardrails.evaluate``) reads these limits before an
action executes: discount cap, spend cap, allowed regions, and whether human approval is
required. The L1-L4 maturity ladder uses ``requires_approval``: an L4 (auto-approve) action
may only auto-approve when it is within policy AND ``requires_approval`` is false; a breach
at any level escalates back to a human gate.

These are workshop defaults — tune them in the Action Center / here to demonstrate the ladder.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "agent_server")

import lakebase as lb  # noqa: E402

# action_type -> (max_discount_pct, max_spend_eur, allowed_regions, requires_approval)
POLICIES = {
    # Commercial
    "quote_send":        (15.0,  None,     ["EMEA", "Americas", "APAC", "China"], True),
    "price_change":      (10.0,  None,     ["EMEA", "Americas", "APAC", "China"], True),
    "crm_task":          (None,  None,     None,                                   False),
    # Supply chain
    "scm_reorder":       (None,  250000.0, ["EMEA", "Americas", "APAC", "China"], True),
    "scm_reroute":       (None,  50000.0,  ["EMEA", "Americas", "APAC", "China"], True),
    "forecast_override": (None,  None,     None,                                   True),
    # Cross-domain
    "escalation":        (None,  None,     None,                                   False),
}


def main() -> None:
    for action_type, (disc, spend, regions, req) in POLICIES.items():
        lb.execute(
            """
            INSERT INTO action_policies
                (action_type, max_discount_pct, max_spend_eur, allowed_regions, requires_approval)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (action_type) DO UPDATE SET
                max_discount_pct = EXCLUDED.max_discount_pct,
                max_spend_eur    = EXCLUDED.max_spend_eur,
                allowed_regions  = EXCLUDED.allowed_regions,
                requires_approval = EXCLUDED.requires_approval
            """,
            (action_type, disc, spend, regions, req),
        )
    print(f"Seeded {len(POLICIES)} action policies into '{lb.PG_SCHEMA}.action_policies'.")
    for at in POLICIES:
        print(f"  - {at}")


if __name__ == "__main__":
    main()

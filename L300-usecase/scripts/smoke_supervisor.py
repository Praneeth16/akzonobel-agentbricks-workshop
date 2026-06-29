"""Smoke-test the supervisor routing + fusion against your lab.

    uv run smoke-supervisor

Runs three canonical questions — one per domain — plus one cross-domain 'why' question,
and prints the routing decision, per-domain legs (via + row counts), and the fused answer.
Requires a configured workspace (auth) and either the Genie space ids or a warehouse for the
text2sql fallback. Audit persistence is best-effort (skipped if Lakebase is unset).
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "agent_server")

from agent_server import supervisor  # noqa: E402

QUESTIONS = [
    "Why did gross margin for Paints EMEA fall in Q2 2026?",
    "Which transport lanes had the worst OTIF last month?",
    "Which key accounts are most at risk of churning?",
    "Did the EMEA margin slip in Q2 line up with any supply or customer-risk signals?",
    "What is the capital of France?",  # out of scope — should decline, query NO domain
]


def main() -> None:
    for q in QUESTIONS:
        print("=" * 88)
        print("Q:", q)
        result = supervisor.supervise(q, persona="controller", persist=True)
        if result.get("out_of_scope"):
            print("Routed to: (out of scope — declined, no domain queried)")
            print("Answer:", result["answer"][:400])
            continue
        routed = [r["domain"] for r in result["routing"]]
        print("Routed to:", routed)
        for leg in result["legs"]:
            note = "  DENIED (governed)" if leg.get("via") == "denied" else ""
            print(f"  - {leg['domain']:<11} via={leg['via']:<12} rows={leg['row_count']}{note}"
                  + (f"  ERROR: {leg['error']}" if leg["error"] else ""))
        print("Answer:", result["answer"][:400])
        print("Recommended action:", result["recommended_action"][:200])
    print("=" * 88)
    print("Done. Full last-result JSON below for reference:")
    print(json.dumps(result, default=str, indent=2)[:2000])


if __name__ == "__main__":
    main()

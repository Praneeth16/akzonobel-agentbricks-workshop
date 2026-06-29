"""Commercial domain sub-agent — built on the same governed leg as Finance.

Customer accounts, churn risk / score, NPS, complaints, sales / revenue by account, and
pipeline, over the governed ``akzo_commercial`` tables. Same NL->SQL leg as Finance,
pointed at the bundled ``commercial_space.md`` (or the real Commercial Genie space when
``COMMERCIAL_SPACE_ID`` is set).
"""
from __future__ import annotations

from ._base import run_leg

DOMAIN = "COMMERCIAL"

ROUTING_DESCRIPTION = (
    "Customer accounts, churn risk/score, NPS, complaints, sales/revenue by account, "
    "pipeline. Use for customer-risk, retention, or account-impact questions."
)

REFRAME_HINT = (
    "at-risk accounts, churn score, complaints, NPS, account revenue trend"
)


def call(question: str, genie_w=None) -> dict:
    """Run the Commercial leg. ``question`` should be framed in commercial terms."""
    return run_leg(DOMAIN, question, genie_w=genie_w)

"""Supply Chain (SCM) domain sub-agent — built on the same governed leg as Finance.

OTIF (on-time-in-full), inventory health and stockouts, days of supply, transport-lane
lead times, service levels, and backorders, over the governed ``akzo_scm`` tables. Same
NL->SQL leg as Finance, pointed at the bundled ``scm_space.md`` (or the real SCM Genie
space when ``SCM_SPACE_ID`` is set).
"""
from __future__ import annotations

from ._base import run_leg

DOMAIN = "SCM"

ROUTING_DESCRIPTION = (
    "OTIF (on-time-in-full), inventory, stockouts, days of supply, transport lanes, lead "
    "times, service levels, backorders. Use for supply, service, delivery, or fulfilment questions."
)

REFRAME_HINT = (
    "OTIF, service level, backorders, stockouts, lane lead times (never use the word margin)"
)


def call(question: str, genie_w=None) -> dict:
    """Run the SCM leg. ``question`` should be framed in supply-chain terms."""
    return run_leg(DOMAIN, question, genie_w=genie_w)

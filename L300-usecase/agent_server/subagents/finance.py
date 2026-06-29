"""Finance domain sub-agent — REUSED from the L200 ``finance-copilot``.

This is the Finance leg of the Multi-domain Supervisor: gross margin, realized price per
unit, FX translation, COGS / raw-material / freight / energy cost, and budget variance,
over the governed ``akzo_finance`` tables. It is the same governed NL->SQL leg the
finance-copilot app uses, pointed at the bundled ``finance_space.md``.

``ROUTING_DESCRIPTION`` is the one line the supervisor router reads to decide whether this
domain is needed — in a native Agent Bricks Multi-Agent Supervisor this IS the sub-agent's
"description" field. ``REFRAME_HINT`` keeps the supervisor's reframing in this domain's terms.
"""
from __future__ import annotations

from ._base import run_leg

DOMAIN = "FINANCE"

ROUTING_DESCRIPTION = (
    "Gross margin, price / realized price per unit, FX translation, COGS / raw-material / "
    "freight / energy cost, budget variance. Use for any 'why did margin/price/cost change' question."
)

REFRAME_HINT = (
    "gross margin / price-per-unit / FX / COGS cost bridge (raw material, freight, energy)"
)


def call(question: str, genie_w=None) -> dict:
    """Run the Finance leg. ``question`` should already be framed in finance terms."""
    return run_leg(DOMAIN, question, genie_w=genie_w)

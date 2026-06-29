"""Domain sub-agents for the Multi-domain Supervisor.

Each module (finance / scm / commercial) is one governed NL->SQL leg over its domain's
Genie space. ``REGISTRY`` maps the domain key -> the module, so the supervisor can route
by name, read each domain's ``ROUTING_DESCRIPTION`` (the per-sub-agent "description" you
fill in when registering a native Agent Bricks Multi-Agent Supervisor), and reframe a
question into a domain's terms via its ``REFRAME_HINT``.

Finance is the reused L200 ``finance-copilot`` leg; SCM and Commercial are the same leg
against their own spaces.
"""
from __future__ import annotations

from . import commercial, finance, scm

REGISTRY = {
    "FINANCE": finance,
    "SCM": scm,
    "COMMERCIAL": commercial,
}

ROUTING_DESCRIPTION = {d: m.ROUTING_DESCRIPTION for d, m in REGISTRY.items()}
REFRAME_HINT = {d: m.REFRAME_HINT for d, m in REGISTRY.items()}

__all__ = ["REGISTRY", "ROUTING_DESCRIPTION", "REFRAME_HINT", "finance", "scm", "commercial"]

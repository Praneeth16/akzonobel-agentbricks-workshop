"""Shared domain sub-agent leg: real Genie space first, governed text2sql fallback.

The Finance sub-agent is the reused ``finance-copilot`` leg; SCM and Commercial are built
on the SAME pattern against their own Genie spaces. Each domain module (finance.py /
scm.py / commercial.py) is a thin wrapper that fills in its DOMAIN, ROUTING_DESCRIPTION,
and REFRAME_HINT and calls ``run_leg`` here. Keeping the mechanics in one place is what
makes the three sub-agents genuinely the same governed leg, not three copies.

Governance — fail CLOSED. Row-level governance per domain is the whole point of the
supervisor: every read must run under the CALLER's identity, never the app service
principal. So:

  * When a domain has a real Genie space, the leg runs it under the OBO client. A
    permission / authorization failure is returned as a governed "cannot answer under your
    permissions" result. It is NEVER recovered by re-running the query as the service
    principal, which would widen the read past the user's entitlements.
  * The instruction-driven text2sql path is used ONLY when a domain has no Genie space id
    configured at all (a deployment config gap, not a permission denial), and even then it
    executes the generated SQL under the SAME OBO client. With no OBO client (local dev /
    non-SSO caller) it runs under the process identity, which is the documented local-dev
    behaviour, not a production widening.
"""
from __future__ import annotations

from . import _genie, text2sql
from agent_server.utils import get_space_id

# Substrings that mark a Genie failure as an authorization / permission denial (as opposed
# to a transient error). On any of these we MUST NOT fall back to a wider-scoped query.
_PERMISSION_MARKERS = (
    "permission", "denied", "not authorized", "unauthorized", "forbidden",
    "403", "401", "access is denied", "does not have", "privilege",
)


def _is_permission_error(err: Exception) -> bool:
    msg = str(err).lower()
    return any(m in msg for m in _PERMISSION_MARKERS)


def _leg(domain: str, via: str, res: dict) -> dict:
    return {
        "domain": domain, "via": via, "sql": res["sql"], "rows": res["rows"][:50],
        "columns": res["columns"], "row_count": res["row_count"], "error": None,
    }


def _error_leg(domain: str, message: str, governed: bool = False) -> dict:
    return {
        "domain": domain, "via": "denied" if governed else "error",
        "sql": "", "rows": [], "columns": [], "row_count": 0,
        "error": message[:300], "governed_denial": governed,
    }


def run_leg(domain: str, question: str, genie_w=None) -> dict:
    """One domain sub-agent: NL -> governed rows under the caller's identity.

    Returns a structured leg result. Fails closed: a permission denial is surfaced as a
    governed denial, never silently widened to a service-principal read.
    """
    space_id = get_space_id(domain)

    if space_id:
        # Real Genie space under the OBO client. This is the governed path.
        try:
            return _leg(domain, "genie_space", _genie.genie_leg(space_id, question, w=genie_w))
        except Exception as e:
            if _is_permission_error(e):
                # Fail closed — do NOT re-run as the service principal.
                return _error_leg(
                    domain,
                    f"{domain} data is outside your permissions; this leg cannot answer "
                    f"under your identity ({str(e)[:160]}).",
                    governed=True,
                )
            return _error_leg(domain, f"{domain} Genie call failed: {str(e)[:200]}")

    # No Genie space configured for this domain: instruction-driven fallback, executed under
    # the SAME OBO client so the read stays within the caller's entitlements.
    try:
        return _leg(domain, "ai_query",
                    text2sql.ask(question, text2sql.space_path(domain), w=genie_w))
    except Exception as e:
        if _is_permission_error(e):
            return _error_leg(
                domain,
                f"{domain} data is outside your permissions ({str(e)[:160]}).",
                governed=True,
            )
        return _error_leg(domain, f"{domain} leg failed: {str(e)[:200]}")

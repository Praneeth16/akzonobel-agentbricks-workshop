"""The Multi-domain Supervisor core — route -> call domain legs -> fuse one governed answer.

This is the supervisor logic the LangGraph host (``agent.py``) wraps as a tool. It is a
faithful, self-contained reproduction of an Agent Bricks Multi-Agent Supervisor:

  - ROUTER  — one LLM call: given the question + each sub-agent's ``ROUTING_DESCRIPTION``,
              decide which domains to consult and write a domain-framed subquestion for each.
  - LEGS    — each chosen domain sub-agent runs its governed NL->SQL leg (real Genie space
              under OBO, or the text2sql fallback). A failing leg degrades, never sinks.
  - FUSER   — one LLM call: fuse the legs' structured rows (not free text) into ONE governed
              answer + ONE recommended action, grounded only in the retrieved numbers.

Row-level governance is per domain: when a real Genie space id is set, the leg's SQL runs
under the caller's identity (OBO), so a UC row filter / column mask narrows what each
persona sees. The ``PERSONAS`` map records the governed scope on the trace.

The per-domain ``ROUTING_DESCRIPTION`` lines ARE the per-sub-agent "description" field you
fill in when registering each Genie space with a native MAS. Editing them re-routes.
"""
from __future__ import annotations

import json
import uuid

import databricks_client as dbx
from databricks.sdk import WorkspaceClient

from agent_server import subagents

SERVICE_IDENTITY = "supervisor-agent@service"  # app/service write identity in the audit trail

# Persona -> the governed data scope the trace notes. OBO at the Genie-call layer (reads only):
# the same routing runs, but each leg's SQL executes under the caller's identity, so a UC row
# filter narrows what each persona actually sees.
PERSONAS = {
    "controller": {
        "label": "Group Controller",
        "scope": "all regions (EMEA / Americas / APAC / China)",
    },
    "emea_planner": {
        "label": "EMEA Supply Planner",
        "scope": "EMEA only — UC row filter on margin_actuals / otif enforced under this identity",
    },
    "rep": {
        "label": "Account Rep",
        "scope": "own accounts only — commercial rows filtered to this rep's book under OBO",
    },
}


def _user_genie_client(user_token: str | None):
    """A WorkspaceClient bound to the END USER's forwarded token (OBO), so Genie reads run
    under the caller's identity / row filters. Falls back to the app service principal when
    no token is present (local dev / non-SSO callers)."""
    if not user_token:
        return dbx.client()
    # auth_type='pat' forces token-only auth so the SP OAuth in the app env does not collide
    # with the forwarded user token ("more than one authorization method").
    return WorkspaceClient(host=dbx.client().config.host, token=user_token, auth_type="pat")


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------
def _build_router_prompt(question: str, descriptions: dict) -> str:
    lines = "\n".join(f"- {d}: {desc}" for d, desc in descriptions.items())
    return (
        "You are the routing controller for an AkzoNobel Multi-Agent Supervisor. "
        "Registered domain subagents:\n"
        f"{lines}\n\n"
        "Decide which subagent(s) are needed to fully answer the user's question. A cross-domain "
        "'why' question often needs several. For EACH chosen domain, also write a focused "
        "subquestion phrased ENTIRELY in that domain's own terms (e.g. ask SCM about OTIF / lead "
        "times / stockouts / service level — never about 'margin'; ask Commercial about churn / "
        "at-risk accounts; ask Finance about the margin/price/cost bridge), so the domain agent does "
        "not decline it as out of scope.\n\n"
        "If the question is NOT about any of these domains (e.g. general knowledge, chit-chat, or "
        "another business area entirely), return an EMPTY domains list with \"out_of_scope\": true. "
        "Do NOT route an unrelated question to a domain just to have something to answer.\n\n"
        "Output ONLY a JSON object, no prose:\n"
        '{"domains": ["FINANCE"|"SCM"|"COMMERCIAL", ...], '
        '"out_of_scope": false, '
        '"reasons": {"FINANCE": "<why this domain>", ...}, '
        '"subquestions": {"FINANCE": "<domain-specific question>", ...}}\n\n'
        f"Question: {question}"
    )


def _strip_json(raw: str) -> str:
    t = raw.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    return t.strip()


def _reframe_subquestion(question: str, domain: str) -> str:
    """Reframe the user's question into the domain's own terms so its Genie space answers it
    rather than declining it as out of scope."""
    raw = dbx.chat(
        messages=[{"role": "user", "content": (
            f"The user asked: \"{question}\"\n\n"
            f"Rewrite it as a focused data question for the AkzoNobel {domain} analytics space, "
            f"which covers ONLY: {subagents.REFRAME_HINT[domain]}. Keep the same subject/scope "
            f"(e.g. Paints EMEA, the relevant quarter/month) but ask ONLY for this domain's "
            "metrics. Output ONLY the rewritten question, one line, no preamble."
        )}],
        max_tokens=160,
    )
    return raw.strip().strip('"')


def route(question: str, descriptions: dict | None = None) -> dict:
    """NL question -> routing decision {domains, out_of_scope, reasons, subquestions}.

    An empty/blank question, an unparseable router response, or a question the router marks
    as unrelated all resolve to out_of_scope=True with NO domains — the supervisor then
    declines gracefully instead of querying every Genie space."""
    descriptions = descriptions or subagents.ROUTING_DESCRIPTION
    if not (question or "").strip():
        return {"domains": [], "out_of_scope": True, "reasons": {}, "subquestions": {}}
    raw = dbx.chat(
        messages=[{"role": "user", "content": _build_router_prompt(question, descriptions)}],
        max_tokens=900,
    )
    try:
        decision = json.loads(_strip_json(raw))
    except Exception:
        # Unparseable router output: treat as out of scope rather than fanning out to every
        # domain (which would run three governed Genie queries for a question we can't route).
        return {"domains": [], "out_of_scope": True, "reasons": {},
                "subquestions": {}, "router_parse_error": True}
    decision["domains"] = [d for d in decision.get("domains", []) if d in subagents.REGISTRY]
    if not decision["domains"]:
        # No valid domain selected -> out of scope. Do NOT default to all domains.
        decision["out_of_scope"] = True
        decision.setdefault("reasons", {})
        decision.setdefault("subquestions", {})
        return decision
    decision["out_of_scope"] = False
    decision.setdefault("reasons", {})
    subqs = decision.get("subquestions") or {}
    # Finance handles margin/price/cost questions natively, so it keeps the user's own question;
    # SCM and Commercial decline finance-framed questions, so they get a reframed subquestion.
    for d in decision["domains"]:
        if d == "FINANCE":
            subqs[d] = question
        elif not subqs.get(d):
            subqs[d] = _reframe_subquestion(question, d)
    decision["subquestions"] = subqs
    return decision


# ---------------------------------------------------------------------------
# FUSER
# ---------------------------------------------------------------------------
def fuse(question: str, decision: dict, legs: list[dict]) -> dict:
    evidence = json.dumps(
        {lr["domain"]: {"sql": lr["sql"], "rows": lr["rows"], "error": lr["error"]} for lr in legs},
        default=str,
    )
    prompt = (
        "You are the AkzoNobel Multi-Agent Supervisor. You consulted these domain subagents and got "
        "governed data.\n"
        f"Routing decision: {json.dumps(decision)}\n"
        f"Retrieved evidence (per domain, as JSON): {evidence}\n\n"
        "Fuse ONE answer to the user's question using ONLY the numbers above (do not invent figures). "
        "If multiple domains contributed, explicitly CONNECT them rather than listing them separately. "
        "Then give ONE concrete recommended action. If the data cannot answer the question, say so.\n\n"
        "Output ONLY a JSON object, no prose, no markdown fences:\n"
        '{"answer": "<= 200 words, the fused governed answer>", '
        '"recommended_action": "<one concrete next step>"}\n\n'
        f"User question: {question}"
    )
    raw = dbx.chat(messages=[{"role": "user", "content": prompt}], max_tokens=1200)
    try:
        parsed = json.loads(_strip_json(raw))
        return {"answer": parsed.get("answer", "").strip(),
                "recommended_action": parsed.get("recommended_action", "").strip()}
    except Exception:
        return {"answer": raw.strip(), "recommended_action": ""}


# ---------------------------------------------------------------------------
# SUPERVISE — full turn: route -> call chosen legs -> fuse -> (optionally) persist
# ---------------------------------------------------------------------------
def supervise(question: str, persona: str = "controller", user_token: str | None = None,
              persist: bool = True) -> dict:
    """Full supervisor turn. Returns the routing trace, per-domain legs, fused answer +
    recommended action, the persona scope note, and (when ``persist`` and Lakebase is
    configured) the persisted session id/uuid."""
    persona_info = PERSONAS.get(persona, PERSONAS["controller"])
    genie_w = _user_genie_client(user_token)

    decision = route(question)

    # Out of scope: decline gracefully WITHOUT querying any Genie space.
    if decision.get("out_of_scope") or not decision["domains"]:
        return {
            "session_id": None,
            "session_uuid": str(uuid.uuid4()),
            "question": question,
            "persona": persona,
            "persona_scope": f"{persona_info['label']} — governed scope: {persona_info['scope']}.",
            "routing": [],
            "legs": [],
            "out_of_scope": True,
            "answer": (
                "That question is outside the scope of this supervisor, which covers AkzoNobel "
                "Finance (margin, price, FX, cost), Supply Chain (OTIF, inventory, lead times), "
                "and Commercial (churn, accounts, NPS). Ask about one of those and I will route "
                "it to the right domain."
            ),
            "recommended_action": "",
        }

    legs = [
        subagents.REGISTRY[d].call(decision["subquestions"].get(d) or question, genie_w=genie_w)
        for d in decision["domains"]
    ]
    fused = fuse(question, decision, legs)

    routing = [
        {"domain": d, "reason": decision["reasons"].get(d, "selected by router")}
        for d in decision["domains"]
    ]

    session_uuid = str(uuid.uuid4())
    session_id = None
    if persist:
        try:
            session_id = _persist_session(session_uuid, question, decision["domains"], fused["answer"])
        except Exception:
            # Audit is best-effort: a missing/unset Lakebase must not sink the answer.
            session_id = None

    return {
        "session_id": session_id,
        "session_uuid": session_uuid,
        "question": question,
        "persona": persona,
        "persona_scope": f"{persona_info['label']} — governed scope: {persona_info['scope']} "
        f"(OBO at the Genie-call layer, reads only).",
        "routing": routing,
        "legs": [
            {"domain": lr["domain"], "via": lr.get("via"), "sql": lr["sql"], "rows": lr["rows"],
             "columns": lr["columns"], "row_count": lr["row_count"], "error": lr["error"]}
            for lr in legs
        ],
        "answer": fused["answer"],
        "recommended_action": fused["recommended_action"],
    }


# ---------------------------------------------------------------------------
# LAKEBASE — audit (agent_sessions) + human feedback (agent_feedback)
# ---------------------------------------------------------------------------
def _persist_session(session_uuid: str, question: str, domains: list[str], answer: str):
    """Log the supervisor turn to akzo.agent_sessions. Returns the new session_id."""
    import lakebase as lb

    row = lb.execute(
        """INSERT INTO agent_sessions (session_uuid, user_email, question, routed_domains, fused_answer)
           VALUES (%s, %s, %s, %s, %s) RETURNING session_id""",
        (session_uuid, dbx.current_user(), question, ",".join(domains), answer),
        returning=True,
    )
    return row["session_id"]


def record_feedback(session_uuid: str, rating: int, note: str | None = None) -> dict:
    """Write a thumbs up/down (+ optional note) to akzo.agent_feedback."""
    import lakebase as lb

    row = lb.execute(
        """INSERT INTO agent_feedback (session_uuid, user_email, rating, comment)
           VALUES (%s, %s, %s, %s) RETURNING feedback_id, created_at""",
        (session_uuid, dbx.current_user(), rating, note),
        returning=True,
    )
    return {"feedback_id": row["feedback_id"], "created_at": str(row["created_at"])}

"""AkzoNobel L300 Multi-domain Supervisor — the flagship.

A LangGraph supervisor that routes each question to the right domain (Finance / Supply
Chain / Commercial), consults each chosen domain's governed Genie space, and fuses ONE
governed answer. It is wrapped in the MLflow ``ResponsesAgent`` interface so it gets
tracing, evaluation, and serving for free — the same wrapper that takes the L100 LangGraph
ReAct agent and the L200 OpenAI Agents SDK agent. Any framework, any model, no lock-in.

The graph has TWO governed tools:
  - ``ask_supervisor`` — the read plane: route -> per-domain Genie legs -> fused answer,
    with the full routing + per-domain SQL/rows trace returned for citation.
  - ``propose_action`` — the act plane: stage a governed action through the Action Plane
    (status ``proposed``) behind the L1-L4 approval ladder. Never executes directly; a
    human (or, at L4, policy) approves and executes it in the Action Center.

Nothing is hardcoded to a workspace. The catalog, schema, LLM endpoint, Genie space ids,
warehouse, and Lakebase instance all come from the environment (see ``agent_server/utils.py``),
so the same code runs unchanged on any lab workspace (e.g. Vocareum) or your own.
"""
from __future__ import annotations

import json
from typing import Any

import mlflow
from databricks_langchain import ChatDatabricks
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import ResponsesAgentRequest, ResponsesAgentResponse

from agent_server import supervisor
from agent_server.utils import get_llm_endpoint

# Trace every LangChain/LangGraph step into the active MLflow experiment.
mlflow.langchain.autolog()

LLM_ENDPOINT = get_llm_endpoint()

SYSTEM_PROMPT = (
    "You are the AkzoNobel Multi-domain Supervisor. You answer cross-functional questions "
    "about AkzoNobel's coatings business by routing to three governed domain sub-agents — "
    "Finance (margin / price / FX / cost), Supply Chain (OTIF / inventory / lead times), and "
    "Commercial (churn / accounts / NPS) — each backed by its own Genie space.\n\n"
    "For ANY question about the business data, call `ask_supervisor` exactly once. It routes "
    "the question to the right domain(s), runs each domain's governed SQL, and returns a fused "
    "answer plus the full routing + per-domain trace. Ground your reply ONLY in what it returns "
    "— never invent figures. Always surface which domains were consulted and cite the numbers.\n\n"
    "If the user wants to ACT on the finding (send a quote, raise a PO, reroute supply, open a "
    "ticket, notify a channel), call `propose_action` to stage it through the governed Action "
    "Plane. This only PROPOSES the action; a human approves and executes it in the Action Center. "
    "Never claim an action was executed — say it has been proposed and is awaiting approval.\n\n"
    "If a question is outside Finance, Supply Chain, and Commercial, say so plainly rather than "
    "guessing."
)


@tool
def ask_supervisor(question: str, persona: str = "controller") -> str:
    """Route a business question across the AkzoNobel Finance, Supply Chain, and Commercial
    Genie spaces and return ONE governed, fused answer with the full per-domain trace.

    Use this for any question about margin, price, FX, cost, OTIF, inventory, lead times,
    stockouts, churn, at-risk accounts, NPS, complaints, or account revenue — including
    cross-domain 'why' questions that span several of these. ``persona`` is the governed
    data scope (controller | emea_planner | rep); it is recorded on the trace.

    Returns a JSON string with: answer, recommended_action, routing (domains + reasons),
    legs (per-domain via/sql/rows), persona_scope, and session_uuid.
    """
    result = supervisor.supervise(question, persona=persona, persist=True)
    return json.dumps(result, default=str)


@tool
def propose_action(action_type: str, subject: str, region: str, payload: dict,
                   level: int = 2) -> str:
    """Stage a governed action through the Action Plane (status ``proposed``) and return its
    guardrail verdict. This does NOT execute the action — a human approves and executes it
    in the Action Center, or at maturity level L4 a within-policy action may auto-approve.

    ``action_type`` is one of: quote_send, price_change, forecast_override, scm_reorder,
    scm_reroute, crm_task, escalation. ``subject`` is a short human label. ``region`` scopes
    the action for guardrails. ``payload`` carries the action's fields (e.g. discount_pct,
    spend_eur, supplier, sku, qty, to, message). ``level`` is the L1-L4 autonomy tier.

    Returns a JSON string with the proposed action row, the guardrail verdict
    (passed/breaches/checks), and the L1-L4 ladder decision. A guardrail breach escalates the
    action immediately. The supervisor never executes the action itself — approval and
    execution happen in the Action Center (or, at L4 within policy, via the /api/act path).
    Returns an error string if the Action Plane is not configured.
    """
    try:
        from action_plane import ESCALATE, ActionPlane, decide, evaluate
    except Exception as e:  # noqa: BLE001 — Action Plane needs Lakebase configured
        return json.dumps({"error": f"action plane unavailable: {e}"})
    ap = ActionPlane()
    action = ap.propose(
        agent="supervisor-agent", action_type=action_type, subject=subject,
        payload=payload, region=region, requested_by="supervisor-agent", level=level,
    )
    verdict = evaluate(action)
    decision = decide(action, verdict)
    # Fail closed at propose time: a breaching action is escalated, not left silently proposed.
    # The supervisor tool never auto-approves/executes (that is the Action Center / /api/act).
    if decision["decision"] == ESCALATE:
        action = ap.escalate(action["id"], reason=decision["reason"], actor="guardrails")
    return json.dumps({"action": action, "guardrail": verdict, "ladder": decision}, default=str)


_graph = create_react_agent(
    ChatDatabricks(endpoint=LLM_ENDPOINT),
    tools=[ask_supervisor, propose_action],
    prompt=SYSTEM_PROMPT,
)


def _to_lc_messages(request: ResponsesAgentRequest) -> list[dict[str, Any]]:
    """Map a ResponsesAgent request to LangChain-style message dicts."""
    items = [i.model_dump() if hasattr(i, "model_dump") else i for i in request.input]
    return [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in items]


def _final_text(graph_output: dict[str, Any]) -> str:
    """Extract the assistant's final text from a LangGraph result."""
    final = graph_output["messages"][-1]
    text = getattr(final, "content", None)
    if text is None and isinstance(final, dict):
        text = final.get("content")
    return text if isinstance(text, str) else str(text)


class AkzoSupervisorAgent(ResponsesAgent):
    """LangGraph multi-domain supervisor exposed through the MLflow ResponsesAgent interface."""

    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        out = _graph.invoke({"messages": _to_lc_messages(request)})
        return ResponsesAgentResponse(
            output=[{
                "id": "msg-1",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": _final_text(out)}],
            }]
        )


AGENT = AkzoSupervisorAgent()

# Models-from-code entry point: `mlflow.pyfunc.log_model(python_model="agent.py", ...)`
# discovers the agent through this call.
mlflow.models.set_model(AGENT)

"""FastAPI app for the Multi-domain Supervisor — a thin REST surface over the supervisor core.

Serves the JSON API under ``/api/*``. The supervisor's read plane (``/api/ask``) routes a
question across the Finance / SCM / Commercial Genie spaces and fuses one governed answer;
the act plane (``/api/act``, ``/api/actions``, approve/reject/execute) is the Action Plane.

This is the simple host for local dev and Apps. For MLflow-served / Responses-API streaming,
use ``agent_server/start_server.py`` (the ``ResponsesAgent`` server).

Run locally:  uvicorn agent_server.main:app --reload --port 8000  (with the CLI profile env set)
In Databricks Apps: app.yaml runs uvicorn on $DATABRICKS_APP_PORT.
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import databricks_client as dbx
from agent_server import supervisor
from agent_server.actions_api import build_actions_router

app = FastAPI(title="AkzoNobel Multi-domain Supervisor Agent")

# Action Plane routes — /api/act, /api/actions, approve, reject, execute, ladder.
app.include_router(build_actions_router("supervisor-agent"))

# CORS so the Vite/Next dev server can call the API during local frontend dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskReq(BaseModel):
    question: str
    persona: Optional[str] = "controller"


class FeedbackReq(BaseModel):
    session_uuid: str
    rating: int  # +1 thumbs up, -1 thumbs down
    note: Optional[str] = None


@app.get("/api/health")
def health():
    return {"status": "ok", "identity": dbx.current_user(), "personas": list(supervisor.PERSONAS.keys())}


@app.post("/api/ask")
def ask(req: AskReq, request: Request):
    if not req.question.strip():
        raise HTTPException(400, "question is required")
    # OBO: Databricks Apps forwards the signed-in user's access token; the Genie legs read
    # under that identity (row filters / personas apply). Absent (local/curl) -> app SP.
    user_token = request.headers.get("X-Forwarded-Access-Token")
    try:
        return supervisor.supervise(req.question, req.persona or "controller", user_token=user_token)
    except Exception as e:
        raise HTTPException(500, f"ask failed: {e}")


@app.post("/api/feedback")
def feedback(req: FeedbackReq):
    if not req.session_uuid:
        raise HTTPException(400, "session_uuid is required")
    try:
        return supervisor.record_feedback(req.session_uuid, req.rating, req.note)
    except Exception as e:
        raise HTTPException(500, f"feedback failed: {e}")

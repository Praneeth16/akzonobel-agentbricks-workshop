"""Characterization tests for the ported Action Plane.

These run with NO Databricks or Lakebase connection: a tiny in-memory fake
stands in for the `action_plane.lakebase` module, so the state machine, the
transactional atomicity of each transition, separation of duties, and the
`evaluate()` guardrail engine can be exercised purely locally. This is the
safety net the plan calls for before re-pointing connectors (U8 execution note).

Run:  pytest L200-capabilities/tests
"""
from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from action_plane import guardrails, lakebase
from action_plane.model import (
    APPROVED,
    EXECUTED,
    EXECUTING,
    PROPOSED,
    REJECTED,
    ActionPlane,
    IllegalTransition,
    SeparationOfDuties,
)


class FakeDB:
    """In-memory stand-in for the lakebase module, with transactional semantics.

    Supports the SQL shapes the Action Plane issues, plus `transaction()`, which
    buffers actions/events writes and only applies them on a clean commit — so a
    mid-transaction failure (e.g. the audit-event INSERT raising) rolls the whole
    transition back. `fail_event_after` injects exactly that fault.
    """

    def __init__(self) -> None:
        self.actions: dict[int, dict] = {}
        self.events: list[dict] = []
        self.policies: dict[str, dict] = {}
        self._next_action_id = 1
        self._next_event_id = 1
        # Fault injection: raise on the action_events INSERT for this event name.
        self.fail_event: str | None = None

    # --- committed-store accessors -----------------------------------------
    def _do_query(self, store_actions, store_events, sql, params):
        s = " ".join(sql.split())
        if s.startswith("SELECT * FROM actions WHERE id ="):
            row = store_actions.get(params[0])
            return [dict(row)] if row else []
        if s.startswith("SELECT id, action_id, ts, event, actor, detail FROM action_events"):
            aid = params[0]
            return [dict(e) for e in store_events if e["action_id"] == aid]
        if s.startswith("SELECT * FROM action_policies WHERE action_type ="):
            pol = self.policies.get(params[0])
            return [dict(pol)] if pol else []
        if s.startswith("SELECT * FROM actions"):
            return [dict(a) for a in store_actions.values()]
        raise AssertionError(f"unexpected query: {s}")

    def _do_execute(self, store_actions, store_events, counters, sql, params, returning):
        s = " ".join(sql.split())
        if s.startswith("INSERT INTO actions"):
            aid = counters["action"]
            counters["action"] += 1
            (agent, action_type, subject, payload, status, level, region, requested_by) = params
            row = {
                "id": aid, "agent": agent, "action_type": action_type,
                "subject": subject, "payload": payload, "status": status,
                "level": level, "region": region, "requested_by": requested_by,
                "approved_by": None, "external_ref": None, "result": None,
            }
            store_actions[aid] = row
            return dict(row)
        if s.startswith("INSERT INTO action_events"):
            action_id, event, actor, detail = params
            if self.fail_event is not None and event == self.fail_event:
                raise RuntimeError(f"injected audit-event failure for '{event}'")
            eid = counters["event"]
            counters["event"] += 1
            store_events.append({
                "id": eid, "action_id": action_id, "ts": eid,
                "event": event, "actor": actor, "detail": detail,
            })
            return None
        if s.startswith("UPDATE actions SET"):
            aid, expected = params[-2], params[-1]
            row = store_actions.get(aid)
            if row is None or row["status"] != expected:
                return None  # lost the race / stale state
            row["status"] = params[0]
            if "approved_by = %s" in s:
                row["approved_by"] = params[1]
            if "external_ref = %s" in s:
                row["result"] = params[1]
                row["external_ref"] = params[2]
            elif "result = %s" in s:
                row["result"] = params[1]
            return dict(row)
        raise AssertionError(f"unexpected execute: {s}")

    # --- autocommit entry points -------------------------------------------
    def query(self, sql, params=None):
        return self._do_query(self.actions, self.events, sql, params)

    def execute(self, sql, params=None, returning=False):
        counters = {"action": self._next_action_id, "event": self._next_event_id}
        out = self._do_execute(self.actions, self.events, counters, sql, params, returning)
        self._next_action_id, self._next_event_id = counters["action"], counters["event"]
        return out

    # --- transactional entry point -----------------------------------------
    @contextmanager
    def transaction(self):
        # Work on deep-ish copies; commit (swap in) only on a clean exit.
        staged_actions = {k: dict(v) for k, v in self.actions.items()}
        staged_events = list(self.events)
        counters = {"action": self._next_action_id, "event": self._next_event_id}

        outer = self

        class Txn:
            def query(self, sql, params=None):
                return outer._do_query(staged_actions, staged_events, sql, params)

            def execute(self, sql, params=None, returning=False):
                return outer._do_execute(
                    staged_actions, staged_events, counters, sql, params, returning
                )

        try:
            yield Txn()
        except Exception:
            # Rollback: discard staged writes entirely.
            raise
        else:
            # Commit: publish the staged state.
            self.actions = staged_actions
            self.events = staged_events
            self._next_action_id = counters["action"]
            self._next_event_id = counters["event"]


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(lakebase, "query", fake.query)
    monkeypatch.setattr(lakebase, "execute", fake.execute)
    monkeypatch.setattr(lakebase, "transaction", fake.transaction)
    return fake


def _seed_policy(db, action_type, **kw):
    db.policies[action_type] = {
        "action_type": action_type,
        "max_discount_pct": kw.get("max_discount_pct"),
        "max_spend_eur": kw.get("max_spend_eur"),
        "allowed_regions": kw.get("allowed_regions"),
        "requires_approval": kw.get("requires_approval", True),
    }


# --- state machine ---------------------------------------------------------

def test_happy_path_proposed_to_executed(db):
    ap = ActionPlane()
    a = ap.propose("agent", "email_notify", "Hi", {"to": "x@y.z"}, "EMEA", "alice")
    assert a["status"] == PROPOSED
    ap.approve(a["id"], approver="bob")
    assert db.actions[a["id"]]["status"] == APPROVED
    ap.mark_executing(a["id"])
    assert db.actions[a["id"]]["status"] == EXECUTING
    ap.mark_executed(a["id"], result={"ok": True}, external_ref="REF-1")
    assert db.actions[a["id"]]["status"] == EXECUTED
    events = [e["event"] for e in db.events if e["action_id"] == a["id"]]
    assert events == ["proposed", "approved", "executing", "executed"]


def test_cannot_execute_without_approval(db):
    ap = ActionPlane()
    a = ap.propose("agent", "email_notify", "Hi", {}, "EMEA", "alice")
    with pytest.raises(IllegalTransition):
        ap.mark_executing(a["id"])


def test_reject_is_terminal(db):
    ap = ActionPlane()
    a = ap.propose("agent", "email_notify", "Hi", {}, "EMEA", "alice")
    ap.reject(a["id"], approver="bob", reason="not now")
    assert db.actions[a["id"]]["status"] == REJECTED
    with pytest.raises(IllegalTransition):
        ap.approve(a["id"], approver="bob")


def test_escalate_then_approve(db):
    ap = ActionPlane()
    a = ap.propose("agent", "quote_send", "Q", {}, "EMEA", "alice")
    ap.escalate(a["id"], reason="guardrail breach")
    assert db.actions[a["id"]]["status"] == "escalated"
    ap.approve(a["id"], approver="bob")
    assert db.actions[a["id"]]["status"] == APPROVED


# --- atomicity (P1) --------------------------------------------------------

def test_transition_failure_midway_leaves_no_unapproved_executable_action(db):
    """If the audit-event INSERT fails after the status UPDATE, the WHOLE
    transition must roll back. An action must never end up 'approved' with no
    'approved' event — otherwise the executor (which checks only status) would
    run an effectively unapproved action."""
    ap = ActionPlane()
    a = ap.propose("agent", "email_notify", "Hi", {"to": "x@y.z"}, "EMEA", "alice")

    # Inject a failure on the 'approved' audit event.
    db.fail_event = "approved"
    with pytest.raises(RuntimeError):
        ap.approve(a["id"], approver="bob")

    # Rolled back: still proposed, no approved event, and NOT executable.
    assert db.actions[a["id"]]["status"] == PROPOSED
    events = [e["event"] for e in db.events if e["action_id"] == a["id"]]
    assert "approved" not in events
    # The executor's precondition (status == approved) is not met → cannot execute.
    with pytest.raises(IllegalTransition):
        ap.mark_executing(a["id"])

    # And a clean approve afterwards both flips status AND records the event together.
    db.fail_event = None
    ap.approve(a["id"], approver="bob")
    assert db.actions[a["id"]]["status"] == APPROVED
    events = [e["event"] for e in db.events if e["action_id"] == a["id"]]
    assert events.count("approved") == 1


# --- separation of duties (P2) ---------------------------------------------

def test_proposer_cannot_approve_own_action_in_model(db):
    ap = ActionPlane()
    a = ap.propose("agent", "email_notify", "Hi", {}, "EMEA", "alice")
    with pytest.raises(SeparationOfDuties):
        ap.approve(a["id"], approver="alice")
    # Untouched: still proposed, no approved event.
    assert db.actions[a["id"]]["status"] == PROPOSED
    assert not [e for e in db.events if e["event"] == "approved"]


def test_proposer_cannot_reject_own_action_in_model(db):
    ap = ActionPlane()
    a = ap.propose("agent", "email_notify", "Hi", {}, "EMEA", "alice")
    with pytest.raises(SeparationOfDuties):
        ap.reject(a["id"], approver="alice", reason="no")
    assert db.actions[a["id"]]["status"] == PROPOSED


# --- guardrails ------------------------------------------------------------

def test_unknown_action_type_breaches(db):
    verdict = guardrails.evaluate({"action_type": "nope", "region": "EMEA", "payload": {}})
    assert verdict["passed"] is False
    assert any("not allowed" in b for b in verdict["breaches"])


def test_spend_over_cap_breaches(db):
    _seed_policy(db, "quote_send", max_spend_eur=50000.0, allowed_regions=["EMEA"])
    verdict = guardrails.evaluate({
        "action_type": "quote_send", "region": "EMEA",
        "payload": json.dumps({"amount_eur": 99999}),
    })
    assert verdict["passed"] is False
    assert any("exceeds cap" in b for b in verdict["breaches"])


def test_region_out_of_scope_breaches(db):
    _seed_policy(db, "quote_send", allowed_regions=["EMEA"])
    verdict = guardrails.evaluate({
        "action_type": "quote_send", "region": "APAC", "payload": {},
    })
    assert verdict["passed"] is False
    assert any("not in allowed regions" in b for b in verdict["breaches"])


def test_within_policy_passes(db):
    _seed_policy(db, "quote_send", max_spend_eur=50000.0, allowed_regions=["EMEA"])
    verdict = guardrails.evaluate({
        "action_type": "quote_send", "region": "EMEA",
        "payload": {"amount_eur": 1000},
    })
    assert verdict["passed"] is True
    assert verdict["breaches"] == []


def test_non_numeric_discount_is_a_breach_not_an_exception(db):
    """A non-numeric discount on a discount-capped action must become a guardrail
    breach (so the action escalates), never an unhandled exception that leaves an
    approved action stuck approved."""
    _seed_policy(db, "quote_send", max_discount_pct=15.0, allowed_regions=["EMEA"])
    verdict = guardrails.evaluate({
        "action_type": "quote_send", "region": "EMEA",
        "payload": {"discount_pct": "not-a-number"},
    })
    assert verdict["passed"] is False
    assert any("not a valid number" in b for b in verdict["breaches"])


def test_non_numeric_discount_with_no_cap_does_not_raise(db):
    """Even with no discount cap, a malformed discount must not raise."""
    _seed_policy(db, "email_notify", allowed_regions=["EMEA"])
    verdict = guardrails.evaluate({
        "action_type": "email_notify", "region": "EMEA",
        "payload": {"discount_pct": "junk"},
    })
    # No cap → discount rule is not applicable → no breach from it.
    assert verdict["passed"] is True

"""In-memory proof of the Action Plane governance contract — no Databricks, no Postgres.

Run:  python3 scripts/test_action_ladder.py   (from the L300-usecase/ root)

Uses a fake in-memory Lakebase to prove, without a workspace:
  * the L1-L4 ladder decision: a breach escalates at any level; L4 within policy
    auto-approves; L4 with a breach still escalates; L1-L3 need human approval;
  * atomicity: a crash between a state transition and its audit event rolls BOTH back,
    so an action can never be left approved/executed without its `action_events` row.

This is the workshop's regression guard for the governance fixes; keep it green.
"""
from __future__ import annotations

import contextlib
import copy
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "agent_server"))


class _Cursor:
    def __init__(self, db, fail_on_event=False):
        self.db, self.fail_on_event = db, fail_on_event
        self._last = None
        self._rows: list = []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SET search_path"):
            return
        if s.startswith("INSERT INTO actions "):
            aid = self.db["_seq"]; self.db["_seq"] += 1
            agent, atype, subject, payload, status, level, region, requested_by = params
            row = {"id": aid, "agent": agent, "action_type": atype, "subject": subject,
                   "payload": payload, "status": status, "level": level, "region": region,
                   "requested_by": requested_by, "approved_by": None, "result": None,
                   "external_ref": None}
            self.db["actions"][aid] = row
            self._last = dict(row)
        elif s.startswith("INSERT INTO action_events"):
            if self.fail_on_event:
                raise RuntimeError("simulated crash between transition UPDATE and event INSERT")
            aid = params[0]
            self.db["events"].setdefault(aid, []).append(
                {"action_id": aid, "event": params[1], "actor": params[2], "detail": params[3]})
            self._last = None
        elif s.startswith("UPDATE actions SET"):
            new_status, aid, prev = params[0], params[-2], params[-1]
            row = self.db["actions"].get(aid)
            if row is None or row["status"] != prev:
                self._last = None
                return
            row["status"] = new_status
            if "approved_by = %s" in s:
                row["approved_by"] = params[1]
            self._last = dict(row)
        elif s.startswith("SELECT * FROM actions WHERE id"):
            row = self.db["actions"].get(params[0])
            self._rows = [dict(row)] if row else []
        elif s.startswith("SELECT * FROM action_policies"):
            pol = self.db["policies"].get(params[0])
            self._rows = [dict(pol)] if pol else []
        else:
            self._rows = []

    def fetchone(self):
        return self._last

    def fetchall(self):
        return self._rows


class _FakeLakebase(types.ModuleType):
    PG_SCHEMA = "akzo"
    INSTANCE_NAME = "test"

    def __init__(self):
        super().__init__("lakebase")
        self.db = {"actions": {}, "events": {}, "policies": {}, "_seq": 1}
        self.fail_event = False

    def query(self, sql, params=None):
        cur = _Cursor(self.db); cur.execute(sql, params); return cur.fetchall()

    def execute(self, sql, params=None, returning=False):
        cur = _Cursor(self.db); cur.execute(sql, params)
        return cur.fetchone() if returning else None

    @contextlib.contextmanager
    def transaction(self):
        snapshot = copy.deepcopy(self.db)
        cur = _Cursor(self.db, fail_on_event=self.fail_event)
        try:
            yield cur
        except Exception:
            self.db.clear(); self.db.update(snapshot)  # rollback both UPDATE + event
            raise


def main() -> None:
    lb = _FakeLakebase()
    sys.modules["lakebase"] = lb

    from action_plane import (AUTO_APPROVE, ESCALATE, NEEDS_APPROVAL, ActionPlane,
                              decide, evaluate)

    lb.db["policies"]["scm_reorder"] = {
        "action_type": "scm_reorder", "max_discount_pct": None, "max_spend_eur": 250000.0,
        "allowed_regions": ["EMEA"], "requires_approval": True}
    lb.db["policies"]["crm_task"] = {
        "action_type": "crm_task", "max_discount_pct": None, "max_spend_eur": None,
        "allowed_regions": None, "requires_approval": False}

    ap = ActionPlane()
    ok = []

    breach = ap.propose("sup", "scm_reorder", "big", {"amount_eur": 999999}, "EMEA", "sup", 2)
    assert decide(breach, evaluate(breach))["decision"] == ESCALATE
    ok.append("breach (any level) -> ESCALATE")

    l4 = ap.propose("sup", "crm_task", "task", {}, "EMEA", "sup", 4)
    assert decide(l4, evaluate(l4))["decision"] == AUTO_APPROVE
    ok.append("L4 within policy -> AUTO_APPROVE")

    l4b = ap.propose("sup", "scm_reorder", "big", {"amount_eur": 999999}, "EMEA", "sup", 4)
    assert decide(l4b, evaluate(l4b))["decision"] == ESCALATE
    ok.append("L4 + breach -> ESCALATE (breach overrides level)")

    l2 = ap.propose("sup", "scm_reorder", "ok", {"amount_eur": 1000}, "EMEA", "sup", 2)
    assert decide(l2, evaluate(l2))["decision"] == NEEDS_APPROVAL
    ok.append("L1-L3 within policy -> NEEDS_APPROVAL")

    atomic = ap.propose("sup", "scm_reorder", "ok", {"amount_eur": 1000}, "EMEA", "sup", 2)
    before = (ap.get(atomic["id"])["status"], len(lb.db["events"].get(atomic["id"], [])))
    lb.fail_event = True
    crashed = False
    try:
        ap.approve(atomic["id"], approver="someone")
    except RuntimeError:
        crashed = True
    lb.fail_event = False
    after = (ap.get(atomic["id"])["status"], len(lb.db["events"].get(atomic["id"], [])))
    assert crashed and before == after == ("proposed", before[1])
    ok.append("mid-transition crash rolls back BOTH (no approved-but-unaudited action)")

    print("\n".join(f"  PASS: {p}" for p in ok))
    print(f"\nALL {len(ok)} ACTION-PLANE GOVERNANCE CHECKS PASSED")


if __name__ == "__main__":
    main()

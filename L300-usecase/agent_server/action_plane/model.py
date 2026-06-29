"""Action Plane — the canonical action record + state machine over Lakebase.

This is the *one governed plane* every AkzoNobel agent acts through. An agent
`propose()`s an action (status `proposed`); a human (or, at L4, policy) drives it
through `approved → executing → executed`, or it `rejected`/`escalated`/`failed`.
Every transition appends an `action_events` row, so the full lineage of who did
what, when, and why is always reconstructable from `action_events`.

State machine (enforced — illegal transitions raise):

    proposed ──approve──▶ approved ──mark_executing──▶ executing ──mark_executed──▶ executed
       │                     │                            │
       ├──reject──▶ rejected │                            └──mark_failed──▶ failed
       │                     │
       └──escalate─┐         └──escalate──▶ escalated
                   ▼
               escalated  (also reachable from approved/executing on a guardrail breach)

`escalated` is reachable from any non-terminal state: a guardrail breach found
at any point pulls the action back to a human gate rather than letting it run.
"""
from __future__ import annotations

import json
from typing import Any

import lakebase

# ----------------------------------------------------------------------------
# State machine
# ----------------------------------------------------------------------------

PROPOSED = "proposed"
APPROVED = "approved"
EXECUTING = "executing"
EXECUTED = "executed"
REJECTED = "rejected"
FAILED = "failed"
ESCALATED = "escalated"

TERMINAL = {EXECUTED, REJECTED, FAILED}

# Legal status transitions. `escalated` is added to every non-terminal source
# below because a guardrail breach can pull any live action to a human gate.
_TRANSITIONS: dict[str, set[str]] = {
    PROPOSED: {APPROVED, REJECTED, ESCALATED},
    APPROVED: {EXECUTING, REJECTED, ESCALATED},
    EXECUTING: {EXECUTED, FAILED, ESCALATED},
    ESCALATED: {APPROVED, REJECTED},
    EXECUTED: set(),
    REJECTED: set(),
    FAILED: set(),
}


class IllegalTransition(Exception):
    """Raised when a requested status transition is not allowed by the machine."""


class ActionNotFound(Exception):
    """Raised when an action_id does not exist."""


def _as_jsonb(value: Any) -> str | None:
    """psycopg adapts a Python str into a jsonb column when the column is jsonb;
    we json.dumps dicts/lists here so callers can pass native objects."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


class ActionPlane:
    """Thin, stateless facade over the Lakebase `actions` + `action_events` tables.

    Methods open their own short-lived connection via the shared `lakebase`
    module, so an instance is cheap and safe to share. All writes record an
    `action_events` row in the *same* call as the `actions` mutation.
    """

    # -- read -----------------------------------------------------------------

    def get(self, action_id: int) -> dict[str, Any]:
        """Return the action row plus its ordered `events` list. Raises if absent."""
        rows = lakebase.query("SELECT * FROM actions WHERE id = %s", (action_id,))
        if not rows:
            raise ActionNotFound(f"action {action_id} not found")
        action = rows[0]
        action["events"] = lakebase.query(
            "SELECT id, action_id, ts, event, actor, detail "
            "FROM action_events WHERE action_id = %s ORDER BY ts, id",
            (action_id,),
        )
        return action

    def list(
        self,
        status: str | None = None,
        agent: str | None = None,
        level: int | None = None,
    ) -> list[dict[str, Any]]:
        """List actions, newest first, optionally filtered by status/agent/level."""
        where: list[str] = []
        params: list[Any] = []
        if status is not None:
            where.append("status = %s")
            params.append(status)
        if agent is not None:
            where.append("agent = %s")
            params.append(agent)
        if level is not None:
            where.append("level = %s")
            params.append(level)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        return lakebase.query(
            f"SELECT * FROM actions{clause} ORDER BY created_at DESC, id DESC",
            tuple(params) if params else None,
        )

    def ladder_counts(self) -> list[dict[str, Any]]:
        """Counts grouped by maturity level + status — feeds the ladder viz."""
        return lakebase.query(
            "SELECT level, status, COUNT(*) AS count "
            "FROM actions GROUP BY level, status ORDER BY level, status"
        )

    # -- internal -------------------------------------------------------------

    def _event(self, action_id: int, event: str, actor: str, detail: Any = None) -> None:
        """Append an audit event in its OWN autocommit write. Used only for a connector
        side-effect note inside the executor, which is not itself a state transition; every
        state transition records its event atomically via `_transition` instead."""
        lakebase.execute(
            "INSERT INTO action_events (action_id, event, actor, detail) "
            "VALUES (%s, %s, %s, %s)",
            (action_id, event, actor, _as_jsonb(detail)),
        )

    def _require(self, action_id: int) -> dict[str, Any]:
        rows = lakebase.query("SELECT * FROM actions WHERE id = %s", (action_id,))
        if not rows:
            raise ActionNotFound(f"action {action_id} not found")
        return rows[0]

    def _check_transition(self, current: str, target: str) -> None:
        if target not in _TRANSITIONS.get(current, set()):
            raise IllegalTransition(
                f"cannot move action from '{current}' to '{target}'"
            )

    def _cas_or_raise(self, row: Any, action_id: int, target: str) -> None:
        """Compare-and-set guard: each transition UPDATE carries `AND status = <read
        status>`, so a concurrent writer that already moved the row makes the UPDATE
        affect 0 rows (row is None). That means we lost the race on a now-stale state
        — raise rather than silently no-op, so terminal/illegal mutations can't slip
        through between the read and the write."""
        if row is None:
            raise IllegalTransition(
                f"action {action_id} changed under us; '{target}' no longer valid"
            )

    def _transition(
        self,
        action_id: int,
        target: str,
        set_sql: str,
        set_params: tuple,
        event: str,
        actor: str,
        detail: Any = None,
    ) -> dict[str, Any]:
        """Run ONE atomic state transition: the status UPDATE (compare-and-set on the read
        status) and its `action_events` INSERT in a single transaction. Either both commit
        or neither does, so a crash between them can never leave an action in a new status
        with no audit row. Validates the transition is legal before touching the DB.

        `set_sql` is the SET clause body (without the leading 'SET'); it must end with
        `status = %s` semantics handled here — callers pass the extra column assignments and
        their params, and this method appends `status = <target>` plus the WHERE guard.
        """
        action = self._require(action_id)
        current = action["status"]
        self._check_transition(current, target)
        with lakebase.transaction() as cur:
            assignments = "status = %s" + (", " + set_sql if set_sql else "")
            params = (target, *set_params, action_id, current)
            cur.execute(
                f"UPDATE actions SET {assignments} WHERE id = %s AND status = %s RETURNING *",
                params,
            )
            row = cur.fetchone()
            self._cas_or_raise(row, action_id, target)
            cur.execute(
                "INSERT INTO action_events (action_id, event, actor, detail) "
                "VALUES (%s, %s, %s, %s)",
                (action_id, event, actor, _as_jsonb(detail)),
            )
        return row

    # -- write / state machine ------------------------------------------------

    def propose(
        self,
        agent: str,
        action_type: str,
        subject: str,
        payload: dict[str, Any],
        region: str,
        requested_by: str,
        level: int = 2,
    ) -> dict[str, Any]:
        """Create a new action in status `proposed` + its first `action_events` row.

        Returns the inserted action row (including its generated `id`).
        """
        # Atomic: the INSERT and its first audit event commit together (or neither does).
        with lakebase.transaction() as cur:
            cur.execute(
                "INSERT INTO actions "
                "(agent, action_type, subject, payload, status, level, region, requested_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (agent, action_type, subject, _as_jsonb(payload), PROPOSED,
                 level, region, requested_by),
            )
            row = cur.fetchone()
            cur.execute(
                "INSERT INTO action_events (action_id, event, actor, detail) "
                "VALUES (%s, %s, %s, %s)",
                (row["id"], "proposed", requested_by,
                 _as_jsonb({"action_type": action_type, "subject": subject, "level": level})),
            )
        return row

    def approve(self, action_id: int, approver: str) -> dict[str, Any]:
        """proposed|escalated → approved. Stamps approved_by + decided_at (atomic w/ audit)."""
        return self._transition(
            action_id, APPROVED,
            "approved_by = %s, decided_at = now()", (approver,),
            event="approved", actor=approver,
        )

    def reject(self, action_id: int, approver: str, reason: str) -> dict[str, Any]:
        """proposed|approved|escalated → rejected (terminal). Records the reason (atomic)."""
        return self._transition(
            action_id, REJECTED,
            "approved_by = %s, decided_at = now()", (approver,),
            event="rejected", actor=approver, detail={"reason": reason},
        )

    def mark_executing(self, action_id: int, actor: str = "executor") -> dict[str, Any]:
        """approved → executing. Only an approved action may begin executing (atomic)."""
        return self._transition(
            action_id, EXECUTING, "", (), event="executing", actor=actor,
        )

    def mark_executed(
        self,
        action_id: int,
        result: dict[str, Any] | None = None,
        external_ref: str | None = None,
        actor: str = "executor",
    ) -> dict[str, Any]:
        """executing → executed (terminal). Records result + the external system ref (atomic)."""
        return self._transition(
            action_id, EXECUTED,
            "result = %s, external_ref = %s, executed_at = now()",
            (_as_jsonb(result), external_ref),
            event="executed", actor=actor,
            detail={"external_ref": external_ref, "result": result},
        )

    def mark_failed(
        self,
        action_id: int,
        result: dict[str, Any] | None = None,
        actor: str = "executor",
    ) -> dict[str, Any]:
        """executing → failed (terminal). Records the failure detail (atomic)."""
        return self._transition(
            action_id, FAILED,
            "result = %s, executed_at = now()", (_as_jsonb(result),),
            event="failed", actor=actor, detail={"result": result},
        )

    def escalate(self, action_id: int, reason: str, actor: str = "guardrails") -> dict[str, Any]:
        """any non-terminal → escalated. The guardrail-breach human gate (atomic w/ audit)."""
        return self._transition(
            action_id, ESCALATED, "", (), event="escalated", actor=actor,
            detail={"reason": reason},
        )

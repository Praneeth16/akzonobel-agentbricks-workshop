"""Action Plane — the shared governed plane every AkzoNobel agent acts through.

    from action_plane import ActionPlane, evaluate, execute

`ActionPlane` is the state machine over Lakebase `actions`/`action_events`;
`evaluate` runs the guardrail policy checks (`action_policies`) before execute;
`execute` (the L3 executor) dispatches an approved action to its connector(s),
routed by `ROUTING` (action_type → connector keys).

At L200 only the email and ticket connectors are enabled and every policy has
`requires_approval = true`, so an action cannot reach `executed` without an
explicit human approval.
"""
from .executor import ROUTING, UnroutableAction, execute
from .guardrails import evaluate
from .model import (
    ActionNotFound,
    ActionPlane,
    IllegalTransition,
    SeparationOfDuties,
    APPROVED,
    EXECUTED,
    EXECUTING,
    ESCALATED,
    FAILED,
    PROPOSED,
    REJECTED,
)

__all__ = [
    "ActionPlane",
    "evaluate",
    "execute",
    "ROUTING",
    "UnroutableAction",
    "ActionNotFound",
    "IllegalTransition",
    "SeparationOfDuties",
    "PROPOSED",
    "APPROVED",
    "EXECUTING",
    "EXECUTED",
    "REJECTED",
    "FAILED",
    "ESCALATED",
]

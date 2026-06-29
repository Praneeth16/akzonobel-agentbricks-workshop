"""Tool connectors — one per external system the Action Plane acts on.

At L200 only two connectors are enabled — email and ticket — the lowest blast
radius pair. L300 adds the rest (crm, erp_po, sharepoint, teams).

Each connector module exposes `send(payload: dict) -> {ref_id, system, raw, via}`
that maps an action payload to its mock endpoint body and POSTs it through a
governed path (UC HTTP connection, or SP-direct fallback).

`SYSTEMS` maps a stable connector key → the module, so the executor can dispatch
by name and apps/UI can introspect the available connectors.
"""
from __future__ import annotations

from . import email, ticket
from ._http import ConnectorError

SYSTEMS = {
    "email": email,
    "ticket": ticket,
}

__all__ = [
    "SYSTEMS",
    "ConnectorError",
    "email",
    "ticket",
]

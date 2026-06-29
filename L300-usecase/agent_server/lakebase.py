"""Lakebase (managed Postgres) access — the shared write-back / audit module.

This is the *write* governance plane for the supervisor: the audit tables
(``agent_sessions``, ``agent_feedback``) and the Action Plane tables
(``actions``, ``action_events``, ``action_policies``) all live here. A short-lived
DB credential (the app/service write identity) is generated via the SDK; psycopg3,
sslmode=require, search_path set to the ``akzo`` schema.

The credential is short-lived (~1h), so we cache it and transparently refresh on
expiry. ``query()`` / ``execute()`` open a fresh autocommit connection per call.

Nothing is hardcoded to a workspace: the instance name, db name, and schema come from
the environment (``LAKEBASE_INSTANCE`` / ``LAKEBASE_DBNAME`` / ``LAKEBASE_SCHEMA``).
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import sql as psql
from psycopg.rows import dict_row

from databricks_client import client, current_user

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE", "")
DB_NAME = os.environ.get("LAKEBASE_DBNAME", "databricks_postgres")
PG_SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "akzo")

_lock = threading.Lock()
_host: str | None = None
_token: str | None = None
_token_exp: float = 0.0
# Refresh a little before the ~1h expiry to avoid mid-request failures.
_TOKEN_TTL_SECONDS = 45 * 60


def _require_instance() -> str:
    if not INSTANCE_NAME:
        raise RuntimeError(
            "LAKEBASE_INSTANCE is not set — set it in app.yaml / .env to use the audit + action tables."
        )
    return INSTANCE_NAME


def _read_write_host() -> str:
    global _host
    if _host is None:
        with _lock:
            if _host is None:
                inst = client().database.get_database_instance(name=_require_instance())
                _host = inst.read_write_dns
    return _host


def _db_token() -> str:
    """Short-lived Lakebase credential — the app/service write identity. Cached + refreshed."""
    global _token, _token_exp
    now = time.time()
    if _token is None or now >= _token_exp:
        with _lock:
            if _token is None or time.time() >= _token_exp:
                cred = client().database.generate_database_credential(
                    instance_names=[_require_instance()]
                )
                _token = cred.token
                _token_exp = now + _TOKEN_TTL_SECONDS
    return _token


def _open(autocommit: bool) -> psycopg.Connection:
    """Open a psycopg connection. Retries once with a fresh token if the cached
    credential has expired."""
    def _connect() -> psycopg.Connection:
        return psycopg.connect(
            host=_read_write_host(), port=5432, dbname=DB_NAME,
            user=current_user(), password=_db_token(), sslmode="require",
            autocommit=autocommit, row_factory=dict_row,
        )

    try:
        return _connect()
    except psycopg.OperationalError:
        # Likely an expired token — force a refresh and retry once.
        global _token
        _token = None
        return _connect()


@contextmanager
def connection():
    """Open an autocommit psycopg connection with search_path set to the akzo schema.

    Rows come back as dicts. Transparently retries once with a fresh token if the
    cached credential has expired.
    """
    conn = _open(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(psql.SQL("SET search_path TO {}").format(psql.Identifier(PG_SCHEMA)))
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    """Open a NON-autocommit connection and yield a cursor inside ONE transaction.

    Commits once on clean exit, rolls back on any exception. Use this to make a state
    transition and its audit-event INSERT atomic: either both land or neither does, so an
    action can never end up approved/executed without its `action_events` row. Rows come
    back as dicts; the akzo search_path is set before the body runs.
    """
    conn = _open(autocommit=False)
    try:
        with conn.cursor() as cur:
            cur.execute(psql.SQL("SET search_path TO {}").format(psql.Identifier(PG_SCHEMA)))
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    finally:
        conn.close()


def query(sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
    """Run a read query, return list-of-dicts."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params: tuple | None = None, returning: bool = False):
    """Run a write. If returning=True, fetch and return the first row (a dict)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        if returning:
            return cur.fetchone()
        return None

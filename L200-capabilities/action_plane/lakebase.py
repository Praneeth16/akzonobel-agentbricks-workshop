"""Lakebase (managed Postgres) access for the Action Plane.

This is the *write* governance plane: a short-lived DB credential (the app /
service write identity) minted via the SDK, psycopg3, sslmode=require, with
search_path set to the actions schema. The credential is short-lived (~1h), so
it is cached and transparently refreshed on expiry. `query()` / `execute()` open
a fresh autocommit connection per call — simple and correct for an app's low
write volume.

Nothing about a workspace is hardcoded. Configure entirely from the environment:

    LAKEBASE_INSTANCE   required at runtime; your Lakebase instance name
                        (on Vocareum this is your assigned instance)
    LAKEBASE_DBNAME     optional; default "databricks_postgres"
    LAKEBASE_SCHEMA     optional; default "akzo_actions"
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
from databricks.sdk import WorkspaceClient

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE")
DB_NAME = os.environ.get("LAKEBASE_DBNAME", "databricks_postgres")
PG_SCHEMA = os.environ.get("LAKEBASE_SCHEMA", "akzo_actions")

_lock = threading.Lock()
_client: WorkspaceClient | None = None
_host: str | None = None
_token: str | None = None
_token_exp: float = 0.0
# Refresh a little before the ~1h expiry to avoid mid-request failures.
_TOKEN_TTL_SECONDS = 45 * 60


def _require_instance() -> str:
    if not INSTANCE_NAME:
        raise RuntimeError(
            "LAKEBASE_INSTANCE is not set. Set it to your Lakebase instance name "
            "(on a Vocareum lab, your assigned instance) before using the Action Plane."
        )
    return INSTANCE_NAME


def client() -> WorkspaceClient:
    global _client
    if _client is None:
        _client = WorkspaceClient()
    return _client


def current_user() -> str:
    return client().current_user.me().user_name


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
    def _connect() -> psycopg.Connection:
        return psycopg.connect(
            host=_read_write_host(), port=5432, dbname=DB_NAME,
            user=current_user(), password=_db_token(), sslmode="require",
            autocommit=autocommit, row_factory=dict_row,
        )

    try:
        conn = _connect()
    except psycopg.OperationalError:
        # Likely an expired token — force a refresh and retry once.
        global _token
        _token = None
        conn = _connect()

    with conn.cursor() as cur:
        cur.execute(
            psql.SQL("SET search_path TO {}").format(psql.Identifier(PG_SCHEMA))
        )
    return conn


@contextmanager
def connection():
    """Open an autocommit psycopg connection with search_path set to PG_SCHEMA.

    Rows come back as dicts. Transparently retries once with a fresh token if the
    cached credential has expired.
    """
    conn = _open(autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    """Open a NON-autocommit connection and wrap the block in one transaction.

    Use this when several writes must commit or roll back together — most
    importantly a state transition UPDATE and its `action_events` audit INSERT,
    which must be atomic so a status can never advance without its audit row.
    Commits on a clean exit; rolls back on any exception.

    Yields a `Txn` whose `query`/`execute` reuse the same connection.
    """
    conn = _open(autocommit=False)
    try:
        yield Txn(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class Txn:
    """A query/execute facade bound to one open transaction's connection."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def query(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def execute(self, sql: str, params: tuple | None = None, returning: bool = False):
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            if returning:
                return cur.fetchone()
            return None


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

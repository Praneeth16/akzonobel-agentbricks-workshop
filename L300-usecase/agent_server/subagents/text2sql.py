"""Text2SQL — the shared natural-language-to-governed-SQL leg.

Takes a domain's Genie space instructions (a ``<domain>_space.md`` file) as the system
prompt, asks the chat model to turn an NL question into a single Spark SQL statement,
executes it on the governed warehouse, and returns {sql, columns, rows, row_count}.

Each domain sub-agent (finance / scm / commercial) reuses this by pointing
``genie_instructions_path`` at its own ``*_space.md`` (these live next to this file so the
package is self-contained). This is the *fallback* path: when a domain's real Genie space
id is set, the sub-agent calls the real space instead (see ``subagents/_genie.py``).

The catalog placeholder ``${AKZO_CATALOG}`` inside the space files is expanded to the
resolved catalog at read time, so nothing is hardcoded to one workspace.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache

import databricks_client as dbx
from agent_server.utils import get_catalog

_HERE = os.path.dirname(os.path.abspath(__file__))

_SYSTEM_PREAMBLE = """You are a Spark SQL generator for a governed Databricks lakehouse.
Use ONLY the tables, columns, and business definitions described below. Never invent columns.
Return a SINGLE Spark SQL statement that answers the question — no commentary, no markdown
fences, no trailing semicolon explanation. If the question cannot be answered from these tables,
return exactly: SELECT 'out_of_scope' AS error.

Domain instructions:
---
{instructions}
---
Output ONLY the SQL.
"""


def space_path(domain: str) -> str:
    """Absolute path to a domain's bundled Genie space instructions file."""
    return os.path.join(_HERE, f"{domain.lower()}_space.md")


@lru_cache(maxsize=8)
def _instructions(path: str) -> str:
    """Read a space file and expand the ${AKZO_CATALOG} placeholder to the live catalog."""
    with open(path, "r") as f:
        text = f.read()
    return text.replace("${AKZO_CATALOG}", get_catalog())


def _strip_sql(text: str) -> str:
    """Pull a clean SQL statement out of a model response (handles code fences)."""
    t = text.strip()
    fence = re.search(r"```(?:sql)?\s*(.+?)```", t, re.DOTALL | re.IGNORECASE)
    if fence:
        t = fence.group(1).strip()
    return t.rstrip(";").strip()


def generate_sql(question: str, genie_instructions_path: str) -> str:
    """NL question -> Spark SQL string, grounded in the domain Genie instructions."""
    system = _SYSTEM_PREAMBLE.format(instructions=_instructions(genie_instructions_path))
    raw = dbx.chat(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        max_tokens=800,
    )
    return _strip_sql(raw)


def ask(question: str, genie_instructions_path: str, w=None) -> dict:
    """NL question -> {sql, columns, rows, row_count}. The full text2sql round trip.

    ``w`` is the end user's OBO WorkspaceClient; the generated SQL is executed under it so the
    read stays inside the caller's Unity Catalog entitlements. The supervisor only uses this
    fallback when a domain has no real Genie space configured (a config gap), never as a
    silent recovery from a Genie permission denial — see ``subagents/_base.py``.
    """
    sql = generate_sql(question, genie_instructions_path)
    result = dbx.run_sql(sql, w=w)
    return {"sql": sql, **result}

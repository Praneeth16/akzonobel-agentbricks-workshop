"""Real Genie-space leg — call a domain's Genie space via the Conversation API.

Genie generates AND runs the governed SQL under the caller's identity (the end user
under OBO when a user WorkspaceClient is passed, otherwise the app service principal),
so Unity Catalog row filters / column masks apply per domain and per persona. Returns
{sql, rows, columns, row_count}.

This is the preferred leg when a domain's ``<DOMAIN>_SPACE_ID`` is configured; otherwise
the domain sub-agent falls back to the instruction-driven ``text2sql`` over the bundled
``*_space.md`` so the leg never goes dark.
"""
from __future__ import annotations

import databricks_client as dbx


def genie_leg(space_id: str, question: str, w=None) -> dict:
    """Call a real Genie space: returns {sql, rows, columns, row_count}.

    ``w`` is the WorkspaceClient the read runs under (end user under OBO when provided);
    None falls back to the app service principal.
    """
    w = w or dbx.client()
    msg = w.genie.start_conversation_and_wait(space_id=space_id, content=question)
    sql, rows, cols = "", [], []
    for att in (msg.attachments or []):
        if getattr(att, "query", None) is None:
            continue
        sql = att.query.query or sql
        att_id = getattr(att, "attachment_id", None)
        res = None
        # Fetch the result; method names vary across SDK versions, so try several.
        for getter in (
            lambda: w.genie.get_message_attachment_query_result(
                space_id=space_id, conversation_id=msg.conversation_id,
                message_id=msg.id, attachment_id=att_id),
            lambda: w.genie.get_message_query_result_by_attachment(
                space_id=space_id, conversation_id=msg.conversation_id,
                message_id=msg.id, attachment_id=att_id),
            lambda: w.genie.get_message_query_result(
                space_id=space_id, conversation_id=msg.conversation_id, message_id=msg.id),
        ):
            try:
                res = getter()
                break
            except Exception:
                continue
        sr = getattr(res, "statement_response", None) if res is not None else None
        if sr and getattr(sr, "result", None) and sr.result.data_array:
            cols = [c.name for c in sr.manifest.schema.columns]
            rows = [dict(zip(cols, r)) for r in sr.result.data_array]
    return {"sql": sql, "rows": rows, "columns": cols, "row_count": len(rows)}

#!/usr/bin/env python3
"""Quick check that a Genie space answers a question, using the Conversation API.
Reads the space ids written by setup_genie_spaces.py.

Usage:
  python3 data/setup/query_genie.py --space finance \
      --question "What was Paints EMEA gross margin percent by month in 2026? Limit to 3 rows."
  # add --profile <profile> only when running from a laptop against a remote workspace
"""
from __future__ import annotations

import argparse
import json
import os

from databricks.sdk import WorkspaceClient

DEFAULTS = {
    "finance": "What was Paints EMEA gross margin percent by month in 2026? Limit to 3 rows.",
    "scm": "Show monthly OTIF for the Rotterdam-NL->EMEA-DACH lane in 2026. Limit to 3 rows.",
    "commercial": "Which Paints EMEA accounts are at churn risk in June 2026? Limit to 3 rows.",
}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"))
    ap.add_argument("--space", default="finance", choices=list(DEFAULTS))
    ap.add_argument("--question", default=None)
    args = ap.parse_args()

    w = WorkspaceClient(profile=args.profile) if args.profile else WorkspaceClient()
    ids = json.load(open(os.path.join(here, "space_ids.json")))
    space_id = ids[args.space]
    question = args.question or DEFAULTS[args.space]

    print(f"Asking {args.space} space {space_id}:\n  {question}\n")
    msg = w.genie.start_conversation_and_wait(space_id, question)
    for att in (msg.attachments or []):
        if att.query and att.query.query:
            print("SQL:\n", att.query.query, "\n")
            res = w.genie.get_message_attachment_query_result(
                space_id, msg.conversation_id, msg.id, att.attachment_id
            )
            result = res.statement_response.result if res.statement_response else None
            if result and result.data_array:
                print("ROWS:")
                for row in result.data_array[:5]:
                    print("  ", row)
        if att.text and att.text.content:
            print("ANSWER:", att.text.content)


if __name__ == "__main__":
    main()

@AGENTS.md

<!-- Loads AGENTS.md into Claude Code. L200-specific guidance lives there. -->

## Hard rules for this tier

- Never hardcode a catalog, workspace URL, CLI profile, SQL warehouse id, or Lakebase instance. This lab runs on Vocareum; every such value comes from an environment variable or a `databricks.yml` bundle variable. The portability test: the code must run unchanged in any workshop attendee's workspace.
- The framework is the OpenAI Agents SDK. Do not swap it for another framework at this tier (L100 is LangGraph, L300 is LangGraph — the mix is deliberate, unified by MLflow `ResponsesAgent`).
- At L200 only the email and ticket connectors are enabled, and every action requires human approval. Do not enable more connectors or auto-approval here; that is L300.
- Run `uv run pytest tests` before changing `action_plane/guardrails.py` or `action_plane/model.py`.

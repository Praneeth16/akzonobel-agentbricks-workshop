---
name: agent-memory
description: "Give the L200 OpenAI Agents SDK agent persistent memory on Lakebase. Use when: (1) User wants the agent to remember across turns or sessions, (2) Questions about session_id / conversation history, (3) 'memory', 'remember', 'persistence', or 'long-term memory'."
---

# Agent Memory (Lakebase)

The L200 agent uses the OpenAI Agents SDK `AsyncDatabricksSession` for memory. Each conversation is keyed by a `session_id`; the SDK stores the turns in the `agent_openai_memory` schema in Lakebase and replays them so the agent has context.

## How it works in this repo

- `agent_server/utils.py` reads the Lakebase config from env (`init_lakebase_config`). If no Lakebase env var is set, memory is **disabled** and the agent runs stateless — useful for a quick local smoke test.
- On each request the agent computes a `session_id` (from `custom_inputs.session_id`, the conversation id, or a fresh uuid) and opens a session.
- `deduplicate_input` sends only the newest turn when the session already holds the history, so context is not double counted.
- `agent_server/start_server.py` calls `_ensure_lakebase_tables()` at startup, so the memory tables are created on first run.

## Turn memory on

1. Set a Lakebase connection in `.env` (see the **lakebase-setup** skill):
   ```bash
   LAKEBASE_INSTANCE_NAME=<your-instance>
   LAKEBASE_AGENT_MEMORY_SCHEMA=agent_openai_memory
   ```
2. Start the agent: `uv run start-app`.
3. Pass a stable `session_id` across turns to keep one conversation:
   ```bash
   curl -X POST http://localhost:8000/invocations \
     -H "Content-Type: application/json" \
     -d '{"input":[{"role":"user","content":"My region is EMEA."}],"custom_inputs":{"session_id":"demo-1"}}'

   curl -X POST http://localhost:8000/invocations \
     -H "Content-Type: application/json" \
     -d '{"input":[{"role":"user","content":"Which region did I say I cover?"}],"custom_inputs":{"session_id":"demo-1"}}'
   ```
   The second answer should recall EMEA.

## Notes

- Memory here is **short-term per session** (conversation history). It is the L200 step; L300 adds richer long-term memory patterns.
- The `session_id` is also written to the MLflow trace metadata, so you can group traces by conversation.
- If you see a 503 "Lakebase unavailable", the schema or the app's SP grant is missing — see **lakebase-setup**.

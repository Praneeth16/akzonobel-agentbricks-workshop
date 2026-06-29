---
name: add-tools
description: "Add tools to the L200 agent and grant the required permissions in databricks.yml. Use when: (1) Adding UC functions, an MCP server, a Genie space, or vector search to the agent, (2) Permission errors at runtime, (3) User says 'add tool', 'connect to', 'grant permission', (4) Configuring databricks.yml resources."
---

# Add Tools & Grant Permissions

> **Auth reminder:** On Vocareum you run inside the workspace, so CLI commands need no profile. Locally, pass `--profile <name>` (read it from `.env`).

The L200 agent gets its tools through **MCP servers built at startup from environment variables** (`agent_server/agent.py` → `_build_mcp_servers()`). You rarely edit the agent code; you set env vars and grant permissions.

## The default: UC-function tools

Every function in `AKZO_CATALOG.AKZO_TOOLS_SCHEMA` is exposed to the agent as a tool through the UC-functions MCP server. To enable:

```bash
# .env (or databricks.yml var for deploy)
AKZO_CATALOG=<your-catalog>
AKZO_TOOLS_SCHEMA=akzo_tools
```

No code change needed. Discover what is there with `uv run discover-tools --catalog $AKZO_CATALOG --schema akzo_tools`.

## Add a Genie space

```bash
AKZO_GENIE_SPACE_ID=01234567-89ab-cdef
```

## Add any other MCP server

`AKZO_MCP_SERVERS` takes `name|path` pairs, separated by `;`:

```bash
AKZO_MCP_SERVERS=Vector Search: docs|/api/2.0/mcp/vector-search/<cat>/akzo_docs;My MCP|https://mcp-my-app.databricksapps.com/mcp
```

## Grant access in databricks.yml

After adding any resource, grant the app access under `resources.apps.akzo_capabilities_agent.resources`. Without this you get permission errors at runtime.

```yaml
resources:
  apps:
    akzo_capabilities_agent:
      resources:
        - name: 'akzo_tools_functions'
          uc_function:
            name: '${var.catalog}.akzo_tools.*'
            permission: 'EXECUTE'
        - name: 'finance_genie'
          genie_space:
            space_id: '01234567-89ab-cdef'
            permission: 'CAN_RUN'
```

See `examples/uc-function.yaml` and `examples/genie-space.yaml`.

## MCP timeouts

Genie is slow; bump its timeout if needed by adding `timeout=60.0` to the `McpServer(...)` call in `agent_server/agent.py`.

## Deploy after changes

```bash
databricks bundle deploy
databricks bundle run akzo_capabilities_agent
```

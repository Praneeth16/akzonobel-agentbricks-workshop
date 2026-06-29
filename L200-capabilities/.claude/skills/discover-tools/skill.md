---
name: discover-tools
description: "Discover available tools and resources in the Databricks workspace. Use when: (1) User asks 'what tools are available', (2) Before wiring tools into the L200 agent, (3) Looking for MCP servers, Genie spaces, UC functions, or vector search indexes, (4) User says 'discover', 'find resources', or 'what can I connect to'."
---

# Discover Available Tools

**Run tool discovery BEFORE wiring tools into the agent** to understand what is available in the workspace. This is the MCP "build" spine: you find the UC functions, then expose them to the agent through the UC-functions MCP server.

## Run Discovery

```bash
uv run discover-tools
```

**Options:**
```bash
# Limit to your workshop catalog
uv run discover-tools --catalog $AKZO_CATALOG

# Limit to the tools schema
uv run discover-tools --catalog $AKZO_CATALOG --schema akzo_tools

# JSON output to a file
uv run discover-tools --format json --output tools.json
```

> The script reads ambient auth (on Vocareum you run inside the workspace, so no `--profile` is needed). Pass `--profile <name>` only if you use a named CLI profile locally.

## What Gets Discovered

| Resource Type | MCP URL Pattern |
|--------------|-----------------|
| **UC Functions** | `{host}/api/2.0/mcp/functions/{catalog}/{schema}` |
| **UC Tables** | (queried via UC functions) |
| **Vector Search Indexes** | `{host}/api/2.0/mcp/vector-search/{catalog}/{schema}` |
| **Genie Spaces** | `{host}/api/2.0/mcp/genie/{space_id}` |
| **Custom MCP Servers** | `{app_url}/mcp` (apps named `mcp-*`) |
| **External MCP Servers** | `{host}/api/2.0/mcp/external/{connection_name}` |

## Next Steps

1. **Add the resource to the agent** — the L200 agent already builds a UC-functions MCP server from `AKZO_CATALOG` + `AKZO_TOOLS_SCHEMA`. Set those and any functions in that schema become tools. To add a Genie space, set `AKZO_GENIE_SPACE_ID`. See **add-tools** for the code + permission grant.
2. **Grant permissions** in `databricks.yml`.
3. **Test locally** with `uv run start-app`.

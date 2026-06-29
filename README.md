<div align="center">

# AkzoNobel Agent Bricks Workshop

### Build production grade AI agents on Databricks, one tier at a time.

A progressive, hands on workshop that takes you from calling AI in SQL to a governed multi domain supervisor, on synthetic AkzoNobel coatings data. It ends with a hackathon starter kit your teams can fork.

</div>

---

## What this is

A practical guide to building real AI agents on Databricks, not toy demos. You climb three tiers, and every tier carries the same lifecycle: build, evaluate, govern, deploy, improve. The three capabilities that matter most deepen as you go: the Agent Bricks agent types, the Model Context Protocol (MCP), and agents that take real actions.

> Note: all data is synthetic. Product names, accounts, suppliers, and documents are invented for the workshop.

---

## The ladder

| Tier | Folder | You build |
|---|---|---|
| L100 Foundations | `L100-foundations/` | AI from SQL, the no code Agent Bricks types, your first coded agent, evaluation, and memory |
| L200 Capabilities | `L200-capabilities/` | Tool calling, an MCP server you build, Lakebase memory, deployment, and the first agent that acts behind a human approval gate |
| L300 Use case | `L300-usecase/` | The flagship multi domain supervisor across Finance, Supply Chain, and Commercial, with the full action ladder and production monitoring |
| Hackathon kit | `hackathon-starter-kit/` | Forkable tracks, starter prompts, ai dev kit skills, and the event hub app |

Each tier is self contained. Start at L100, or jump in where you need to.

---

## The three spines

The workshop is organized around three capabilities that grow tier over tier.

| Spine | L100 | L200 | L300 |
|---|---|---|---|
| Agent Bricks types | Build the single purpose types | Add tools to a coded agent | Supervisor composes them all |
| MCP | Consume one read only tool | Build and register a server | Wire the full fleet |
| Agents that act | None, read only | One or two connectors with human approval | All connectors, an approval ladder, and an audit trail |
| LLMOps | Evaluation, one judge, tracing | Judge suite, AI Gateway, guardrails | Production monitoring, lineage, advanced evaluation |

---

## Get started

1. Run the shared data setup once. See `data/`. It loads the coatings tables, the document volume, the Genie spaces, and the vector index into Unity Catalog.
2. Open `L100-foundations/` and follow its README.
3. Climb the ladder.

---

## Prerequisites

- Databricks workspace with serverless SQL compute and Unity Catalog
- Foundation Model API access (for example Llama 3.3 70B or Claude Sonnet)
- Vector Search, Lakebase, and Databricks Apps enabled
- Permission to read the workshop catalog

---

## Status

This repository is built tier by tier. L100 foundations is complete and every notebook has been run end to end on a live workspace. L200, L300, the hackathon kit, and the Vocareum course package are built and code-reviewed; their agent/app runtime paths still need in-workspace verification.

| Item | State |
|---|---|
| `data/` generators and `load_to_uc.py` | Run end to end, all 13 tables loaded |
| `data/setup/setup_genie_spaces.py` | Run, three Genie spaces created and answering |
| `data/setup/setup_vector_search.py` | Run, index ready |
| `L100-foundations/00_sql_ai_functions.ipynb` | Built, run on workspace |
| `L100-foundations/01_agent_bricks_types.md` | Built, UI and programmatic paths, prerequisites verified |
| `L100-foundations/02_agent_evaluation.ipynb` | Built, run on workspace |
| `L100-foundations/03_short_term_memory.ipynb` | Built, run on workspace |
| `L100-foundations/L100-agent-langgraph/` | Built (LangGraph + ResponsesAgent + 1 managed MCP tool), codex-reviewed; in-workspace run pending |
| `L200-capabilities/` | Built (OpenAI SDK agent, MCP server, action_plane, Lakebase memory, eval), codex-reviewed; in-workspace run pending |
| `L300-usecase/` | Built (LangGraph supervisor, full action_plane, e2e app, advanced eval), codex-reviewed; in-workspace run pending |
| `hackathon-starter-kit/` | 11 tracks, 11 starter prompts, 6 ai-dev-kit skills, and the relocated AppKit hackathon hub |
| `vocareum-course/` | Serverless Vocareum package: ordered notebooks, learner README, cfg, lifecycle scripts, `.dbc` bundle builder |

---

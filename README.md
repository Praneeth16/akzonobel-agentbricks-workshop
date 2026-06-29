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

### 1. Clone this repo into your Databricks workspace

The whole workshop runs from a Databricks **Git folder** (Repos), so you get the
notebooks, data generators, and starter kit in one place and can pull updates as
new tiers land.

**Option A — UI (recommended)**

1. In your Databricks workspace sidebar, click **Workspace → Users → your user**.
2. Click **Create → Git folder** (top right).
3. Paste the repo URL and confirm the details:
   - **Git repository URL:** `https://github.com/Praneeth16/akzonobel-agentbricks-workshop.git`
   - **Git provider:** GitHub
   - **Branch:** `main`
4. Click **Create Git folder**. The repo clones to
   `/Workspace/Users/<you>/akzonobel-agentbricks-workshop`.
5. To get later updates, open the Git folder and click **⋯ → Git… → Pull**.

> Private repo? Add a GitHub Personal Access Token first under
> **Settings → Linked accounts (Git integration)**, then clone.

**Option B — Databricks CLI (from your laptop)**

```bash
databricks repos create \
  --url https://github.com/Praneeth16/akzonobel-agentbricks-workshop.git \
  --provider gitHub \
  --path /Workspace/Users/<you>/akzonobel-agentbricks-workshop
```

> On **Vocareum**, you don't clone — the course bundle is preloaded. See
> `vocareum-course/` and start from `_AGENDA/00 - Start Here`.

### 2. Run the workshop

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

This repository is built tier by tier. L100 foundations is complete: every notebook has been run end to end on a live workspace, and the L100 coded agent is deployed on Databricks Apps and answered a governed query through its managed MCP tool. L200 and L300 are built, code-reviewed, and made deployable on Databricks Apps (the same four deploy fixes proven on L100); their live app deploy needs the per-deploy catalog variable and the app service-principal grants.

| Item | State |
|---|---|
| `data/` generators and `load_to_uc.py` | Run end to end, all 13 tables loaded |
| `data/setup/setup_genie_spaces.py` | Run, three Genie spaces created and answering |
| `data/setup/setup_vector_search.py` | Run, index ready |
| `L100-foundations/00_sql_ai_functions.ipynb` | Built, run on workspace |
| `L100-foundations/01_agent_bricks_types.md` | Built, UI and programmatic paths, prerequisites verified |
| `L100-foundations/02_agent_evaluation.ipynb` | Built, run on workspace |
| `L100-foundations/03_short_term_memory.ipynb` | Built, run on workspace |
| `L100-foundations/L100-agent-langgraph/` | Built + codex-reviewed + **deployed on Databricks Apps and answered a live governed query** through its managed MCP tool |
| `L200-capabilities/` | Built + codex-reviewed; **deployability fixed** (packaging, catalog-in-Apps, host scheme, startup resilience); deploy with `--var catalog=...` + run `grant-app-access` |
| `L300-usecase/` | Built + codex-reviewed; **deployability fixed** (same four); deploy with `--var catalog=...` + run `grant-app-access` |
| `hackathon-starter-kit/` | 11 tracks, 11 starter prompts, 6 ai-dev-kit skills, and the relocated AppKit hackathon hub |
| `vocareum-course/` | Serverless Vocareum package: ordered notebooks, learner README, cfg, lifecycle scripts, `.dbc` bundle builder |

---

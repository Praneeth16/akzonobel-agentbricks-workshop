# Hackathon Hub

The AkzoNobel Agent Bricks workshop event app, built on [Databricks AppKit](https://databricks.github.io/appkit/) (React + TypeScript + Tailwind). It runs the hackathon flow — **Register → Teams → Submit → Judge → Leaderboard** — with state persisted in Lakebase (managed Postgres), plus read-only catalogue pages (tracks, guides, resources) and a few live "Try it live" SQL panels over the workshop schemas.

> **Portability:** every workspace-specific value (workspace URL, catalog, SQL warehouse, Lakebase instance, Postgres host) is read from environment variables. Nothing is hardcoded, so the hub runs unchanged across workspaces and Vocareum labs. See the env var table below.

**Architecture:**
- `client/` — React frontend (Vite). Catalogue pages read `VITE_*` build-time env vars.
- `server/` — Express backend. `server/routes.ts` exposes `/api/hack/*`; `server/lakebase.ts` connects to Lakebase with short-lived OAuth credentials.
- `config/queries/*.sql` — analytics-plugin SQL for the live panels.

## Prerequisites

- Node.js v22+ and npm
- Databricks CLI (for deployment / auth)
- Access to a Databricks workspace (or a Vocareum lab) with:
  - a SQL warehouse,
  - the workshop catalog holding the `akzo_*` schemas,
  - a Lakebase (classic Database Instance) for the `hack_*` tables.

## Configuration (environment variables)

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Used by | Purpose |
|---|---|---|
| `DATABRICKS_HOST` | server / CLI | Workspace URL. |
| `DATABRICKS_CONFIG_PROFILE` | server | Optional `~/.databrickscfg` profile (omit for `DEFAULT`). |
| `DATABRICKS_WAREHOUSE_ID` | analytics plugin | SQL warehouse that runs `config/queries/*.sql`. |
| `LAKEBASE_INSTANCE` | server | Classic Lakebase Database Instance name (required). |
| `PGHOST` | server | Lakebase Postgres endpoint host (required). |
| `LAKEBASE_DBNAME` / `PGDATABASE` | server | Postgres database (default `databricks_postgres`). |
| `LAKEBASE_SCHEMA` | server | Schema for `hack_*` tables (default `akzo`). |
| `DATABRICKS_CHAT_ENDPOINT` | server | Chat/serving endpoint name (optional). |
| `VITE_DATABRICKS_HOST` | client | Workspace URL shown in the CLI setup step. |
| `VITE_WORKSHOP_CATALOG` | client | Catalog name shown in guides + Resources. |
| `VITE_LAKEBASE_INSTANCE` / `VITE_LAKEBASE_DBNAME` / `VITE_LAKEBASE_SCHEMA` | client | Lakebase details shown on the Resources page. |
| `VITE_REPO_BASE` | client | Base URL for repo file links. |

The live SQL panels reference tables as `schema.table` (e.g. `akzo_finance.margin_actuals`). **Set your SQL warehouse's default catalog to the workshop catalog** so they resolve.

For Databricks Apps deployment, the runtime env values live in `app.yaml` (literals — no `${VAR}` interpolation there); replace the `<placeholder>` values before deploying.

### CLI Authentication

The Databricks CLI requires authentication to deploy and manage apps. Configure authentication using one of these methods:

#### OAuth U2M

Interactive browser-based authentication with short-lived tokens:

```bash
databricks auth login --host https://your-workspace.cloud.databricks.com
```

This will open your browser to complete authentication. The CLI saves credentials to `~/.databrickscfg`.

#### Configuration Profiles

Use multiple profiles for different workspaces:

```ini
[DEFAULT]
host = https://dev-workspace.cloud.databricks.com

[production]
host = https://prod-workspace.cloud.databricks.com
client_id = prod-client-id
client_secret = prod-client-secret
```

Deploy using a specific profile:

```bash
databricks bundle deploy --profile production
```

**Note:** Personal Access Tokens (PATs) are legacy authentication. OAuth is strongly recommended for better security.

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development

Run the app in development mode with hot reload:

```bash
npm run dev
```

The app will be available at the URL shown in the console output.

### Build

Build both client and server for production:

```bash
npm run build
```

This creates:

- `dist/server.js` - Compiled server bundle
- `client/dist/` - Bundled client assets

### Production

Run the production build:

```bash
npm start
```

## Code Quality

There are a few commands to help you with code quality:

```bash
# Type checking
npm run typecheck

# Linting
npm run lint
npm run lint:fix

# Formatting
npm run format
npm run format:fix
```

## Deployment with Databricks Asset Bundles

### 1. Configure Bundle

Update `databricks.yml` with your workspace settings:

```yaml
targets:
  default:
    workspace:
      host: https://your-workspace.cloud.databricks.com
```

Make sure to replace all placeholder values in `databricks.yml` with your actual resource IDs.

### 2. Validate Bundle

```bash
databricks bundle validate
```

### 3. Deploy

Deploy to the default target:

```bash
databricks bundle deploy
```

### 4. Run

Start the deployed app:

```bash
databricks bundle run <APP_NAME> -t dev
```

### Deploy to Production

1. Configure the production target in `databricks.yml`
2. Deploy to production:

```bash
databricks bundle deploy -t prod
```

## Project Structure

```
* client/          # React frontend
  * src/           # Source code
  * public/        # Static assets
* server/          # Express backend
  * server.ts      # Server entry point
  * routes/        # Routes
* shared/          # Shared types
* databricks.yml   # Bundle configuration
* app.yaml         # App configuration
* .env.example     # Environment variables example
```

## Tech Stack

- **Backend**: Node.js, Express
- **Frontend**: React.js, TypeScript, Vite, Tailwind CSS, React Router
- **UI Components**: Radix UI, shadcn/ui
- **Databricks**: AppKit SDK

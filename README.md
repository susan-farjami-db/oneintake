# AI Task Force intake

An intake app where business units at the carrier propose AI, data, and analytics projects. While the requester types, the app flags likely duplicates of existing work. Each new request is classified on submit, and the Task Force reviews, approves, or merges requests. The portfolio is queryable in Genie. All data is synthetic.

## Architecture

```mermaid
flowchart LR
  subgraph App["Databricks App (APX: FastAPI + React)"]
    UI["React UI<br/>submit, mine, review, portfolio"]
    API["FastAPI<br/>OBO identity, rate limit"]
  end
  subgraph LB["Lakebase Postgres (Autoscaling)"]
    APPDB[("app.*<br/>requests, decisions, config")]
    SERV[("serving.*<br/>pgvector embeddings,<br/>projects_synced")]
  end
  subgraph UC["Unity Catalog"]
    RAW[("raw<br/>landing volume, lb_*_history")]
    SILVER[("silver.requests<br/>+ quarantine")]
    GOLD[("gold.projects<br/>gold.portfolio_metrics")]
    OPS[("ops<br/>glossary, BU map, row filter")]
  end
  FM["FM embedding endpoint<br/>databricks-bge-large-en"]
  WH["SQL warehouse<br/>ai_classify 2.1"]
  GENIE["Genie space"]
  UI --> API
  API -- "duplicate search" --> SERV
  API -- "write requests, decisions" --> APPDB
  API -- "embed draft" --> FM
  API -- "classify; KPIs as the user (OBO)" --> WH
  APPDB -- "Lakehouse Sync (CDF)" --> RAW
  GEN["data_gen<br/>synthetic CSV/JSON"] --> RAW
  RAW -- "SDP pipeline (SQL)" --> SILVER --> GOLD
  GOLD -- "ops/run.py sync-projects" --> SERV
  OPS -. "row filter, tags" .-> SILVER & GOLD
  GOLD --> GENIE
  UI -. "Ask Genie" .-> GENIE
```

## Repo map

| Path | What it holds |
|------|---------------|
| `config/` | Form fields, categories, thresholds (packaged into the app) |
| `data_gen/` | Seeded synthetic data; names come from `names.py` |
| `pipeline/` | SDP SQL: bronze, silver (expectations, `ai_extract`, `ai_classify`), gold (embeddings, clusters) |
| `governance/uc_setup.sql` | Schemas, comments, tags, row filter, metric view |
| `lakebase/setup.sql` | Postgres schema, pgvector, app grants |
| `src/oneintake/` | APX app: `backend/` (FastAPI, sqlmodel) and `ui/` (React, shadcn, orval) |
| `ml/` | Classifier evaluation and duplicate-threshold tuning (MLflow) |
| `genie/` | Genie space creation, config, answer check |
| `ops/` | Runner used locally and by jobs |
| `tests/` | Data, governance, API, and Playwright demo-flow checks |
| `evidence/` | Output of every pipeline, check, and evaluation |

## Setup

Requirements: `uv`, `bun`, the Databricks CLI, and a workspace with Lakebase Autoscaling, a SQL warehouse, and FM endpoints.

1. Create `.env` (gitignored) with `DATABRICKS_CONFIG_PROFILE`, `DATABRICKS_SQL_WAREHOUSE_ID`, `INTAKE_CATALOG`, `LAKEBASE_PROJECT`, and `LAKEBASE_BRANCH`. Then load it: `set -a; source .env; set +a`.
2. Set the target's `catalog` variable in `databricks.yml`, then build and deploy:
   ```bash
   uv run apx build
   databricks bundle deploy --profile <profile>
   ```
3. Load data and governance: `databricks bundle run data_setup`. This generates and uploads data, sets up Lakebase and grants, starts Lakehouse Sync, refreshes the pipeline, applies governance and the metric view, and syncs projects.
4. Create the Genie space with `uv run python genie/genie_space.py`. Put the printed id in the target's `genie_space_id` variable and deploy again.
5. Start the app: `databricks bundle run oneintake_app`.
6. Evaluate: `databricks bundle run evaluation` runs the classifier eval, threshold tuning, and Genie answer check.

Local development: `uv run apx dev start` serves the app at `http://127.0.0.1:9002`, using the OBO emulator with your CLI identity.

## Checks

```bash
uv run pytest tests/test_data_gen.py tests/test_api.py      # data rules, live API, latency
uv run pytest tests/test_governance.py                      # comments, tags, row filter as member and non-member
uv run pytest tests/test_demo_flow.py                       # browser demo flow (DEMO_BASE_URL for the deployed app)
uv run python ml/evaluate_classifier.py
uv run python ml/tune_duplicate_threshold.py
```

Decisions are in `ASSUMPTIONS.md` and `DECISIONS.md`. Results are in `BUILD_REPORT.md`.
